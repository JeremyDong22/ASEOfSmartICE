#include "video_decoder.h"
#include "utils.h"

extern "C" {
#include <libavformat/avformat.h>
#include <libavcodec/avcodec.h>
#include <libavutil/imgutils.h>
#include <libswscale/swscale.h>
}

namespace smartice {

struct VideoDecoder::Impl {
    AVFormatContext* format_ctx = nullptr;
    AVCodecContext* codec_ctx = nullptr;
    AVFrame* frame = nullptr;
    AVPacket* packet = nullptr;
    SwsContext* sws_ctx = nullptr;
    int video_stream_idx = -1;

    ~Impl() {
        if (sws_ctx) sws_scale_free(&sws_ctx);
        if (packet) av_packet_free(&packet);
        if (frame) av_frame_free(&frame);
        if (codec_ctx) avcodec_free_context(&codec_ctx);
        if (format_ctx) avformat_close_input(&format_ctx);
    }
};

VideoDecoder::VideoDecoder(const std::string& rtsp_url)
    : rtsp_url_(rtsp_url)
    , running_(false)
    , width_(0)
    , height_(0)
    , fps_(0.0)
    , impl_(std::make_unique<Impl>())
{
    auto logger = get_logger();
    logger->info("VideoDecoder created for RTSP: {}", rtsp_url);
}

VideoDecoder::~VideoDecoder() {
    if (running_) {
        stop();
    }
}

void VideoDecoder::decode_loop() {
    auto logger = get_logger();

    try {
        // Open RTSP stream
        AVDictionary* options = nullptr;
        av_dict_set(&options, "rtsp_transport", "tcp", 0);
        av_dict_set(&options, "max_delay", "500000", 0);  // 500ms
        av_dict_set(&options, "timeout", "5000000", 0);   // 5s

        int ret = avformat_open_input(&impl_->format_ctx, rtsp_url_.c_str(), nullptr, &options);
        av_dict_free(&options);

        if (ret < 0) {
            char errbuf[AV_ERROR_MAX_STRING_SIZE];
            av_strerror(ret, errbuf, sizeof(errbuf));
            logger->error("Failed to open RTSP stream: {}", errbuf);
            running_ = false;
            return;
        }

        // Get stream information
        if (avformat_find_stream_info(impl_->format_ctx, nullptr) < 0) {
            logger->error("Failed to find stream info");
            running_ = false;
            return;
        }

        // Find video stream
        impl_->video_stream_idx = -1;
        for (unsigned int i = 0; i < impl_->format_ctx->nb_streams; i++) {
            if (impl_->format_ctx->streams[i]->codecpar->codec_type == AVMEDIA_TYPE_VIDEO) {
                impl_->video_stream_idx = i;
                break;
            }
        }

        if (impl_->video_stream_idx == -1) {
            logger->error("No video stream found");
            running_ = false;
            return;
        }

        // Get codec
        AVCodecParameters* codecpar = impl_->format_ctx->streams[impl_->video_stream_idx]->codecpar;
        const AVCodec* codec = avcodec_find_decoder(codecpar->codec_id);
        if (!codec) {
            logger->error("Codec not found");
            running_ = false;
            return;
        }

        // Create codec context
        impl_->codec_ctx = avcodec_alloc_context3(codec);
        if (avcodec_parameters_to_context(impl_->codec_ctx, codecpar) < 0) {
            logger->error("Failed to copy codec parameters");
            running_ = false;
            return;
        }

        // Open codec
        if (avcodec_open2(impl_->codec_ctx, codec, nullptr) < 0) {
            logger->error("Failed to open codec");
            running_ = false;
            return;
        }

        // Get video properties
        width_ = impl_->codec_ctx->width;
        height_ = impl_->codec_ctx->height;
        AVRational fps_rational = impl_->format_ctx->streams[impl_->video_stream_idx]->avg_frame_rate;
        fps_ = av_q2d(fps_rational);

        logger->info("Video stream opened: {}x{} @ {:.2f} FPS", width_, height_, fps_);

        // Allocate frame and packet
        impl_->frame = av_frame_alloc();
        impl_->packet = av_packet_alloc();

        // Create SWS context for color conversion
        impl_->sws_ctx = sws_alloc_context();
        av_opt_set_int(impl_->sws_ctx, "srcw", width_, 0);
        av_opt_set_int(impl_->sws_ctx, "srch", height_, 0);
        av_opt_set_int(impl_->sws_ctx, "src_format", impl_->codec_ctx->pix_fmt, 0);
        av_opt_set_int(impl_->sws_ctx, "dstw", width_, 0);
        av_opt_set_int(impl_->sws_ctx, "dsth", height_, 0);
        av_opt_set_int(impl_->sws_ctx, "dst_format", AV_PIX_FMT_BGR24, 0);
        av_opt_set_int(impl_->sws_ctx, "sws_flags", SWS_BILINEAR, 0);

        if (sws_init_context(impl_->sws_ctx, nullptr, nullptr) < 0) {
            logger->error("Failed to initialize SWS context");
            running_ = false;
            return;
        }

        // Main decoding loop
        int frame_count = 0;
        while (running_) {
            ret = av_read_frame(impl_->format_ctx, impl_->packet);
            if (ret < 0) {
                if (ret == AVERROR_EOF) {
                    logger->info("End of stream");
                } else {
                    char errbuf[AV_ERROR_MAX_STRING_SIZE];
                    av_strerror(ret, errbuf, sizeof(errbuf));
                    logger->error("Error reading frame: {}", errbuf);
                }
                break;
            }

            // Process video packets only
            if (impl_->packet->stream_index == impl_->video_stream_idx) {
                ret = avcodec_send_packet(impl_->codec_ctx, impl_->packet);
                if (ret < 0) {
                    logger->error("Error sending packet to decoder");
                    av_packet_unref(impl_->packet);
                    continue;
                }

                while (ret >= 0) {
                    ret = avcodec_receive_frame(impl_->codec_ctx, impl_->frame);
                    if (ret == AVERROR(EAGAIN) || ret == AVERROR_EOF) {
                        break;
                    } else if (ret < 0) {
                        logger->error("Error receiving frame from decoder");
                        break;
                    }

                    // Convert frame to BGR format (OpenCV compatible)
                    cv::Mat frame_bgr(height_, width_, CV_8UC3);
                    uint8_t* dest[1] = { frame_bgr.data };
                    int dest_linesize[1] = { static_cast<int>(frame_bgr.step[0]) };

                    sws_scale(impl_->sws_ctx,
                              impl_->frame->data, impl_->frame->linesize,
                              0, height_,
                              dest, dest_linesize);

                    frame_count++;

                    // Store latest frame
                    {
                        std::lock_guard<std::mutex> lock(frame_mutex_);
                        latest_frame_ = frame_bgr.clone();
                    }

                    // Call callback if provided
                    if (frame_callback_) {
                        frame_callback_(frame_bgr);
                    }
                }
            }

            av_packet_unref(impl_->packet);
        }

        logger->info("Decoded {} frames", frame_count);

    } catch (const std::exception& e) {
        logger->error("Exception in decode loop: {}", e.what());
    }

    running_ = false;
    logger->info("Decode loop stopped");
}

void VideoDecoder::start(FrameCallback callback) {
    auto logger = get_logger();

    if (running_) {
        logger->warn("VideoDecoder already running");
        return;
    }

    logger->info("Starting video decoding");
    frame_callback_ = callback;
    running_ = true;

    // Start decode thread
    decode_thread_ = std::make_unique<std::thread>(&VideoDecoder::decode_loop, this);
}

void VideoDecoder::stop() {
    auto logger = get_logger();
    if (running_) {
        logger->info("Stopping video decoding");
        running_ = false;

        if (decode_thread_ && decode_thread_->joinable()) {
            decode_thread_->join();
        }

        logger->info("Video decoding stopped");
    }
}

bool VideoDecoder::get_latest_frame(cv::Mat& frame) {
    std::lock_guard<std::mutex> lock(frame_mutex_);
    if (latest_frame_.empty()) {
        return false;
    }
    frame = latest_frame_.clone();
    return true;
}

} // namespace smartice

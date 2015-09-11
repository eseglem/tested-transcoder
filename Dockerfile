FROM ubuntu:trusty64

RUN add-apt-repository -y ppa:stebbins/handbrake-releases \
    && add-apt-repository -y ppa:mc3man/trusty-media \
    && apt-get update \
    && apt-get install -y make git mkvtoolnix handbrake-cli mplayer \
    ffmpeg mp4v2-utils linux-headers-generic build-essential dkms supervisor

RUN git clone https://github.com/donmelton/video-transcoding-scripts \
    && mv video-transcoding-scripts/*.sh /usr/local/bin/ \
    && rm -rf video-transcoding-scripts

COPY supervisor-config.conf /etc/supervisor/conf.d/
COPY transcoder.py /usr/local/

RUN mkdir -p /media/transcoder \
    && chmod +x /usr/local/bin/transcoder.py \

CMD ["/usr/bin/supervisord"]
FROM ubuntu:trusty

RUN echo "deb http://ppa.launchpad.net/stebbins/handbrake-releases/ubuntu trusty main" >> /etc/apt/sources.list \ 
    && echo "deb http://ppa.launchpad.net/mc3man/trusty-media/ubuntu trusty main" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install --force-yes -y git mkvtoolnix handbrake-cli mplayer ffmpeg mp4v2-utils

COPY transcoder.py /usr/local/bin/

RUN git clone https://github.com/donmelton/video-transcoding-scripts \
    && mv video-transcoding-scripts/*.sh /usr/local/bin/ \
    && rm -rf video-transcoding-scripts \
    && chmod +x /usr/local/bin/transcoder.py

CMD ["python", "/usr/local/bin/transcoder.py"]

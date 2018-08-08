FROM ntodd/video-transcoding

COPY transcoder.py /usr/local/bin/

ENTRYPOINT ["python", "/usr/local/bin/transcoder.py"]

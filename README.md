#tested-transcoder
Please post feedback on github or at http://www.tested.com/forums/general-discussion/495076-transcoder-feedback/

This is a docker container that serves as a black box for transcoding and repackaging Blu-rays and DVDs ripped using MakeMKV into iTunes quality video files suitable for streaming using Plex or XBMC. It uses Don Melton's video transcoder scripts (https://github.com/donmelton/video-transcoding-scripts) to transcode individual files, but handles a lot of the tedious stuff involved in movie transcoding for you, including adding all audio tracks, and all subtitle tracks, handling the movie crop, etc.

To rip discs, first use MakeMKV to rip only the movie, audio tracks, and subtitles you want. The title with the most chapters, and largest size is typically the one you want. I typically tell MakeMKV to grab all the English language subtitles and audio tracks, which is a generally a good strategy. You can set this as the default in View > Preferences > Language > Preferred Language. The process may take a long time, depending on your computer and the resources you give the black box.

## Prerequisites

* Docker - https://store.docker.com/search?type=edition&offering=community
* MakeMKV - http://www.makemkv.com/download/

## Installation Instructions


## Usage

1. While the container is running, starting your encodes is as easy as dragging a video from MakeMKV into the 'input' folder.
2. When the encode is in progress, you can check in on its progress by looking at the end of the log in the 'work' folder.
3. When the encodes are complete, the new, better compressed video will be in the 'output' folder and the original source MKV will be in the 'completed-originals' folder. After you've confirmed subtitles and audio tracks are correct, you can safely delete the large original file.
4. Enjoy your new, much smaller MKV in your favorite media player.

import logging
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time


def non_zero_min(values):
    "Return the min value but always prefer non-zero values if they exist"
    if len(values) == 0:
        raise TypeError('non_zero_min expected 1 arguments, got 0')
    non_zero_values = [i for i in values if i != 0]
    if non_zero_values:
        return min(non_zero_values)
    return 0


class Transcoder(object):

    # path to mount the virtual box share
    TRANSCODER_ROOT = "/media/transcoder"
    # directory containing new video to transcode
    INPUT_DIRECTORY = TRANSCODER_ROOT + '/input'
    # directory where handbrake will save the output to. this is a temporary
    # location and the file is moved to OUTPUT_DIRECTORY after complete
    WORK_DIRECTORY = TRANSCODER_ROOT + '/work'
    # temporary directory for the original to be moved to while processing.
    # this allows for multiple docker containers to be run on the same folder.
    PROCESSING_DIRECTORY = TRANSCODER_ROOT + '/processing'
    # directory containing the original inputs after they've been transcoded
    COMPLETED_DIRECTORY = TRANSCODER_ROOT + '/completed-originals'
    # directory containing the compressed outputs
    OUTPUT_DIRECTORY = TRANSCODER_ROOT + '/output'
    # directory for storage of crops
    CROP_DIRECTORY = TRANSCODER_ROOT + '/crops'
    # standard options for the transcode-video script from input args. put
    # defaults in first string and all additional arguments will be added.
    TRANSCODE_OPTIONS = ''
    if len(sys.argv) > 1:
        TRANSCODE_OPTIONS += ' '.join(sys.argv[1:])
    # number of seconds a file must remain unmodified in the INPUT_DIRECTORY
    # before it is considered done copying. increase this value for more
    # tolerance on bad network connections.
    WRITE_THRESHOLD = 30
    # path to logfile
    LOGFILE = TRANSCODER_ROOT + '/transcoder.log'

    def __init__(self):
        self.running = False
        self.logger = None
        self.current_command = None
        self._default_handlers = {}

    def setup_signal_handlers(self):
        "Setup graceful shutdown and cleanup when sent a signal"
        def handler(signum, frame):
            self.stop()

        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            self._default_handlers[sig] = signal.signal(sig, handler)

    def restore_signal_handlers(self):
        "Restore the default handlers"
        for sig, handler in self._default_handlers.items():
            signal.signal(sig, handler)
        self._default_handlers = {}

    def execute(self, command):
        # TODO: use Popen and assign to current_command so we can terminate
        args = shlex.split(command)
        out = subprocess.check_output(args=args, stderr=subprocess.STDOUT)
        return out

    def setup_logging(self):
        self.logger = logging.getLogger('transcoder')
        self.logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(self.LOGFILE)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.info('Transcoder started and scanning for input')

    def check_filesystem(self):
        "Checks that the filesystem and logger is setup properly"
        dirs = (self.INPUT_DIRECTORY, self.WORK_DIRECTORY,
                self.OUTPUT_DIRECTORY, self.COMPLETED_DIRECTORY,
                self.PROCESSING_DIRECTORY, self.CROP_DIRECTORY)
        if not all(map(os.path.exists, dirs)):
            for path in dirs:
                if not os.path.exists(path):
                    try:
                        os.mkdir(path)
                    except OSError as ex:
                        msg = 'Cannot create directory "%s": %s' % (
                            path, ex.strerror)
                        sys.stdout.write(msg)
                        sys.stdout.flush()
                        return False

        if not self.logger:
            self.setup_logging()
        return True

    def stop(self):
        # guard against multiple signals being sent before the first one
        # finishes
        if not self.running:
            return
        self.running = False
        self.logger.info('Transcoder shutting down')
        if self.current_command:
            self.current_command.terminate()
        # logging
        logging.shutdown()
        self.logger = None
        # signal handlers
        self.restore_signal_handlers()

    def run(self):
        self.running = True
        self.setup_signal_handlers()

        while self.running:
            if self.check_filesystem():
                self.check_for_input()
            time.sleep(5)

    def check_for_input(self):
        "Look in INPUT_DIRECTORY for an input file and process it"
        for filename in os.listdir(self.INPUT_DIRECTORY):
            if filename.startswith('.'):
                continue
            path = os.path.join(self.INPUT_DIRECTORY, filename)
            if (time.time() - os.stat(path).st_mtime) > self.WRITE_THRESHOLD:
                # when copying a file from windows to the VM, the filesize and
                # last modified times don't change as data is written.
                # fortunately these files seem to be locked such that
                # attempting to open the file for reading raises an IOError.
                # it seems reasonable to skip any file we can't open
                try:
                    f = open(path, 'r')
                    f.close()
                except IOError:
                    continue

                # Race condition could cause IOError, just skip the file, since
                # it is already being process by another worker.
                try:
                    self.process_input(path)
                except IOError:
                    continue

                # move the source to the COMPLETED_DIRECTORY
                dst = os.path.join(self.COMPLETED_DIRECTORY,
                                   os.path.basename(path))
                shutil.move(path, dst)
                break

    def process_input(self, path):
        name = os.path.basename(path)
        self.logger.info('Found new input "%s"', name)

        # move file to a processing directory so it won't be picked up agian
        # possible race condition in paarallel, allow it to raise an error
        processing_path = os.path.join(self.PROCESSING_DIRECTORY,
                                       os.path.basename(path))
        shutil.move(path, processing_path)
        path = processing_path

        # if any of the following functions return no output, something
        # bad happened and we can't continue

        # parse the input meta info.
        meta = self.scan_media(path)
        if not meta:
            return

        # transcode the video
        work_path = self.transcode(path, meta)
        if not work_path:
            return

        # move the completed output to the output directory
        self.logger.info('Moving completed work output %s to output directory',
                         os.path.basename(work_path))
        output_path = os.path.join(self.OUTPUT_DIRECTORY,
                                   os.path.basename(work_path))
        shutil.move(work_path, output_path)
        shutil.move(work_path + '.log', output_path + '.log')

    def scan_media(self, path):
        "Use handbrake to scan the media for metadata"
        name = os.path.basename(path)
        self.logger.info('Scanning "%s" for metadata', name)
        command = 'HandBrakeCLI --scan --input "%s"' % path
        try:
            out = self.execute(command)
        except subprocess.CalledProcessError as ex:
            if 'unrecognized file type' in ex.output:
                self.logger.info('Unknown media type for input "%s"', name)
            else:
                self.logger.info('Unknown error for input "%s" with error: %s',
                                 name, ex.output)
            return None

        # process out
        return out

    def transcode(self, path, meta):
        name = os.path.basename(path)
        output_name = os.path.splitext(name)[0] + '.mkv'
        output = os.path.join(self.WORK_DIRECTORY, output_name)
        # if these paths exist in the work directory, remove them first
        for workpath in (output, output + '.log'):
            if os.path.exists(workpath):
                self.logger.info('Removing old work output: "%s"', workpath)
                os.unlink(workpath)

        #TODO: Parse resolution and determine settings

        #TODO: Get crop from directory
        crop = 'detect'

        command_parts = [
            'transcode-video',
            '--crop ' + crop,
            '--add-audio all',
            '--add-subtitle all',
            self.TRANSCODE_OPTIONS,
            '--output "%s"' % output,
            '"%s"' % path
        ]
        command = ' '.join(command_parts)
        self.logger.info('Transcoding input "%s" with command: %s',
                         path, command)
        try:
            self.execute(command)
        except subprocess.CalledProcessError as ex:
            self.logger.info('Transcoding failed for input "%s": %s',
                             name, ex.output)
            return None
        self.logger.info('Transcoding completed for input "%s"', name)
        return output


if __name__ == '__main__':
    print(len(sys.argv))
    print(sys.argv[1:])
    print(' '.join(sys.argv[1:]))

    transcoder = Transcoder()
    transcoder.run()

import datetime
import logging
import logging.config
import sarge
import sys
import time

logging.config.fileConfig('clone_and_profile.logging.conf')

logger = logging.getLogger(__name__)

application_start_timestamp = time.time()

class CmError(Exception):
    def __init__(self, args, stdout, stderr):
        self.args=args
        self.stdout=stdout
        self.stderr=stderr

def run_command_with_logging(args):

    logger.info(f"Running command: {args}")

    with sarge.Capture(buffer_size=1) as stdout, sarge.Capture(buffer_size=1) as stderr:
        pipeline = sarge.run(args, async_=True, stdout=stdout, stderr=stderr)

        while pipeline.commands[-1].poll() == None:

            stdout_result = stdout.read(block=False)
            if stdout_result != b'':
                logger.info(stdout_result)
            stderr_result = stderr.read(block=False)
            if stderr_result != b'':
                logger.error(stderr_result)

            if stdout_result != b'' or stderr_result != b'':
                time.sleep(0.1)

        stdout_result = stdout.read()
        if stdout_result != b'':
            logger.info(stdout_result)
        stderr_result = stderr.read()
        if stderr_result != b'':
            logger.error(stderr_result)

        if pipeline.commands[-1].poll() != 0:
            raise CmError(args, stdout, stderr)

def create_plastic_repo(plastic_repo_name):
    run_command_with_logging(['cm', 'mkrep', plastic_repo_name])

def sync_git_repo(github_repo_url, plastic_repo_name, github_username, github_password):
    run_command_with_logging(['cm', 'sync', plastic_repo_name, 'git', github_repo_url, f'--user={github_username}', f'--pwd={github_password}'])

def clone_and_profile(github_repo_url, plastic_repo_name, github_username, github_password):
    create_plastic_repo(plastic_repo_name)
    sync_git_repo(github_repo_url, plastic_repo_name, github_username, github_password)


if __name__=='__main__':

    if len(sys.argv) != 5:
        print("Usage: clone_and_profile.py <Github repo URL> <Plastic repo name> <Github username> <Github password>")
        print("Github repo must exist. Plastic repo must not exist.")
        sys.exit(1)
    else:
        github_repo_url = sys.argv[1]
        plastic_repo_name = sys.argv[2]
        github_username = sys.argv[3]
        github_password = sys.argv[4]
        
        clone_and_profile(github_repo_url, plastic_repo_name, github_username, github_password)



import datetime
from enum import Enum, auto
import logging
import logging.config
import numpy
import sys

logging.config.fileConfig('analyze_log.logging.conf')

logger = logging.getLogger(__name__)

def extract_timestamp(line):
    # Example line: 2019-10-13 00:58:39,262 | INFO | b'\rDownloading... / 785109/1841502'

    try:
        return datetime.datetime.strptime(line[0:23], '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return datetime.datetime.strptime(line[0:23], '%Y-%m-%d %H:%M:%S,%f')


def extract_progress(line):
    # Representative line: 2019-10-13 00:56:54,432 | INFO | b'\rDownloading... - 18127/1841502'

    slash_location = line.rfind('/')
    if slash_location != -1:
        space_location = line[0:slash_location].rfind(' ')
        if space_location != -1:
            progress_string = line[space_location + 1:slash_location]
            return int(progress_string)

    return None

class OverallStatisticsState(Enum):
    INITIAL = auto()
    COMPRESSING_OBJECTS = auto()
    DOWNLOADING = auto()
    PROCESSING_OBJECTS = auto()
    IMPORTING = auto()

class TimestampPair:
    def __init__(self, first):
        self.first = first
        self.last = first
    
    def __str__(self):
        return f'first: {self.first}, last: {self.last}, duration: {self.duration()}'
    
    def duration(self):
        return (self.last - self.first).total_seconds()

class ItemTimestampPair:
    def __init__(self, item, timestamp):
        self.item = item
        self.timestamp = timestamp
    
    def __str__(self):
        return f'item: {self.item}, timestamp: {self.timestamp}'

class OverallStatisticsAnalyzer:

    def __init__(self):
        self.state = OverallStatisticsState.INITIAL
        self.timestamp_pairs = {}

        self.identifiers_to_states = {
            'Compressing objects...': OverallStatisticsState.COMPRESSING_OBJECTS,
            'Downloading...': OverallStatisticsState.DOWNLOADING,
            'Processing objects:...': OverallStatisticsState.PROCESSING_OBJECTS,
            'Importing...': OverallStatisticsState.IMPORTING,
        }

    def __str__(self):

        results = []
        for state, timestamp_pair in self.timestamp_pairs.items():
            results.append(f'{state}: {{ {timestamp_pair} }}')

        return ', '.join(results)

    def process_line(self, line):

        for identifier, state in self.identifiers_to_states.items():
            if identifier in line:
                timestamp = extract_timestamp(line)
                if self.state != state:
                    if not state in self.timestamp_pairs:
                        self.timestamp_pairs[state] = TimestampPair(timestamp)
                
                self.timestamp_pairs[state].last = timestamp

                if self.state != OverallStatisticsState.INITIAL:
                    self.timestamp_pairs[self.state].last = timestamp
                self.state = state
                break

    def generate_csv(self):

        compressing_objects_timestamp_pair = self.timestamp_pairs[OverallStatisticsState.COMPRESSING_OBJECTS] if OverallStatisticsState.COMPRESSING_OBJECTS in self.timestamp_pairs else None
        downloading_timestamp_pair = self.timestamp_pairs[OverallStatisticsState.DOWNLOADING] if OverallStatisticsState.DOWNLOADING in self.timestamp_pairs else None
        processing_objects_timestamp_pair = self.timestamp_pairs[OverallStatisticsState.PROCESSING_OBJECTS] if OverallStatisticsState.PROCESSING_OBJECTS in self.timestamp_pairs else None
        importing_timestamp_pair = self.timestamp_pairs[OverallStatisticsState.IMPORTING] if OverallStatisticsState.IMPORTING in self.timestamp_pairs else None

        results = 'Stage,Duration\n'
        results += f'Compressing objects,{compressing_objects_timestamp_pair.duration() if compressing_objects_timestamp_pair else "Unknown"}\n'
        results += f'Downloading,{downloading_timestamp_pair.duration() if downloading_timestamp_pair else "Unknown"}\n'
        results += f'Processing objects,{processing_objects_timestamp_pair.duration() if processing_objects_timestamp_pair else "Unknown"}\n'
        results += f'Importing,{importing_timestamp_pair.duration() if importing_timestamp_pair else "Unknown"}\n'
        
        return results

class BucketAnalyzer:

    def __init__(self):
        self.items_and_timestamps = []

    def process_line(self, line):

        timestamp = extract_timestamp(line)
        progress = extract_progress(line)

        if progress:
            self.items_and_timestamps.append(ItemTimestampPair(progress, timestamp))

    def __str__(self):

        results = []
        for item_and_timestamp in self.items_and_timestamps:
            results.append(f'{{{item_and_timestamp}}}')

        return ', '.join(results)

    def resample_timestamps(self, bucket_size):

        max_item = max(item_and_timestamp.item for item_and_timestamp in self.items_and_timestamps)
        max_sample_location = int((max_item + bucket_size - 1) / bucket_size) * bucket_size

        sampling_locations = numpy.array(range(0, max_sample_location + bucket_size, bucket_size))
        xp = numpy.array(list(item_and_timestamp.item for item_and_timestamp in self.items_and_timestamps))
        yp = numpy.array(list((item_and_timestamp.timestamp - self.items_and_timestamps[0].timestamp).total_seconds() for item_and_timestamp in self.items_and_timestamps))

        resampled_timestamps = numpy.interp(sampling_locations, xp, yp)

        return resampled_timestamps

    def generate_csv(self, bucket_size):

        resampled_timestamps = self.resample_timestamps(bucket_size)

        results = 'Item nr,Average duration per item (s)\n'

        max_item = max(item_and_timestamp.item for item_and_timestamp in self.items_and_timestamps)
        max_sample_location = int((max_item + bucket_size - 1) / bucket_size) * bucket_size

        for bucket_index in range(0, int(max_sample_location / bucket_size)):
            item_index = (bucket_index + 1) * bucket_size
            duration_per_item = (resampled_timestamps[bucket_index + 1] - resampled_timestamps[bucket_index]) / bucket_size
            results += f'{item_index},{duration_per_item}\n'

        return results


class LogParser:
    def __init__(self, overall_statistics_analyzer, download_analyzer, import_analyzer):
        self.overall_statistics_analyzer = overall_statistics_analyzer
        self.download_analyzer = download_analyzer
        self.import_analyzer = import_analyzer

        self.identifiers_to_analyzers = {
            'Compressing objects...': None,
            'Downloading...': download_analyzer,
            'Processing objects:...': None,
            'Importing...': import_analyzer,
        }
    
    def process_line(self, line):
        self.overall_statistics_analyzer.process_line(line)

        for identifier, analyzer in self.identifiers_to_analyzers.items():
            if analyzer and (identifier in line):
                analyzer.process_line(line)

def write_log_file(file_name, content):
    with open(file_name, 'wt') as file:
        file.write(content)

def analyze_log(input_log_file_name, overall_statistics_file_name, download_speed_file_name, import_speed_file_name):

    download_bucket_size = 100000
    import_bucket_size = 1000

    overall_statistics_analyzer = OverallStatisticsAnalyzer()
    download_analyzer = BucketAnalyzer()
    import_analyzer = BucketAnalyzer()

    log_parser = LogParser(overall_statistics_analyzer, download_analyzer, import_analyzer)

    with open(input_log_file_name, 'rt') as log_file:
        for line_number, line in enumerate(log_file):

            log_parser.process_line(line)

    write_log_file(overall_statistics_file_name, overall_statistics_analyzer.generate_csv())
    write_log_file(download_speed_file_name, download_analyzer.generate_csv(download_bucket_size))
    write_log_file(import_speed_file_name, import_analyzer.generate_csv(import_bucket_size))

if __name__=='__main__':

    if len(sys.argv) != 5:
        print("Usage: analyze.py <input log file> <overall statistics csv> <download speed csv> <import speed csv>")
        print("Github repo must exist. Plastic repo must not exist.")
        sys.exit(1)
    else:
        input_log_file_name = sys.argv[1]
        overall_statistics_file_name = sys.argv[2]
        download_speed_file_name = sys.argv[3]
        import_speed_file_name = sys.argv[4]
        
        analyze_log(input_log_file_name, overall_statistics_file_name, download_speed_file_name, import_speed_file_name)

import datetime
import hashlib
import os
import logging
import requests

from kombu import Connection, Exchange
from banzai.utils import import_utils

logger = logging.getLogger('banzai')


def post_to_archive_queue(image_path, broker_url, exchange_name='fits_files'):
    exchange = Exchange(exchange_name, type='fanout')
    with Connection(broker_url) as conn:
        producer = conn.Producer(exchange=exchange)
        producer.publish({'path': image_path})
        producer.release()


def make_output_directory(runtime_context, image_config):
    # Create output directory if necessary
    output_directory = os.path.join(runtime_context.processed_path, image_config.site,
                                    image_config.instrument.name, image_config.epoch)

    if runtime_context.preview_mode:
        output_directory = os.path.join(output_directory, 'preview')
    else:
        output_directory = os.path.join(output_directory, 'processed')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    return output_directory


def get_md5(filepath):
    with open(filepath, 'rb') as file:
        md5 = hashlib.md5(file.read()).hexdigest()
    return md5


def instantly_public(proposal_id):
    public_now = False
    if proposal_id in ['calibrate', 'standard', 'pointing']:
        public_now = True
    if 'epo' in proposal_id.lower():
        public_now = True
    return public_now


def ccdsum_to_filename(image):
    if image.ccdsum is None:
        ccdsum_str = ''
    else:
        ccdsum_str = 'bin{ccdsum}'.format(ccdsum=image.ccdsum.replace(' ', 'x'))
    return ccdsum_str


def filter_to_filename(image):
    return str(image.filter)


def config_to_filename(image):
    filename = str(image.configuration_mode)
    filename = filename.replace('full_frame', '')
    filename = filename.replace('default', '')
    filename = filename.replace('central_2k_2x2', 'center')
    return filename


def telescope_to_filename(image):
    return image.header.get('TELESCOP', '').replace('-', '')


def make_calibration_filename_function(calibration_type, context):
    def get_calibration_filename(image):
        telescope_filename_function = import_utils.import_attribute(context.TELESCOPE_FILENAME_FUNCTION)
        name_components = {'site': image.site, 'telescop': telescope_filename_function(image),
                           'camera': image.header.get('INSTRUME', ''), 'epoch': image.epoch,
                           'cal_type': calibration_type.lower()}
        cal_file = '{site}{telescop}-{camera}-{epoch}-{cal_type}'.format(**name_components)
        for function_name in context.CALIBRATION_FILENAME_FUNCTIONS[calibration_type]:
            filename_function = import_utils.import_attribute(function_name)
            filename_part = filename_function(image)
            if len(filename_part) > 0:
                cal_file += '-{}'.format(filename_part)
        cal_file += '.fits'
        return cal_file
    return get_calibration_filename


def load_remote_image(filename, runtime_context):
    logger.info('Attempting to download image from archive.')

    headers = {'Authorization': 'Token ' + runtime_context.ARCHIVE_API_TOKEN}

    basename = os.path.basename(filename)
    basename = basename[:basename.index('.')]  # remove extension
    start, end = date_range_from_basename(basename)
    url = runtime_context.ARCHIVE_FRAMES_URL + '?basename={0}&start={1}&end={2}'.format(
        basename, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    )
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    response_dict = response.json()

    if not response_dict['results']:
        raise Exception('Could not find file {} locally or remotely'.format(basename))

    frame_url = response_dict['results'][0]['url']
    file_response = requests.get(frame_url)
    file_response.raise_for_status()

    return os.io.BytesIO(file_response.content)


def date_range_from_basename(basename):
    """
    Return a 60 day window around the dateobs of the fits file to use as a
    search contraint on the archive. This is simply to speed up the response.
    """
    date_str = basename.split('-')[2]
    middle_date = datetime.strptime(date_str, '%Y%m%d')
    start = middle_date - datetime.timedelta(days=30)
    end = middle_date + datetime.timedelta(days=30)
    return start, end
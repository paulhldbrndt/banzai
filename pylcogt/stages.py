from __future__ import absolute_import, print_function, division

import os
import itertools

from sqlalchemy.sql import func

from . import dbs
from .utils import date_utils
from . import logs

import abc

__author__ = 'cmccully'


def make_output_directory(processed_path, epoch, telescope):
    # Create output directory if necessary
    output_directory = os.path.join(processed_path, telescope.site,
                                    telescope.instrument, epoch)
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    return


class Stage(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, processed_path='', initial_query=None, group_by=None, logger_name='',
                 log_message='', cal_type='', image_suffix_number='00', previous_suffix_number='00',
                 previous_stage_done=None):
        self.processed_path = processed_path
        self.initial_query = initial_query
        self.group_by = group_by
        self.logger = logs.get_logger(logger_name)
        self.log_message = log_message
        self.cal_type = cal_type
        self.image_suffix_number = image_suffix_number
        self.previous_stage_done = previous_stage_done
        self.previous_image_suffix = previous_suffix_number

    def select_input_images(self, telescope, epoch):
        return dbs.select_input_images(telescope, epoch, self.initial_query, self.previous_stage_done, self.group_by)

    # By default don't return any output images
    def get_output_images(self, telescope, epoch):
        return None

    # By default we don't need to get a calibration image
    def get_calibration_image(self, epoch, telescope, image_config):
        return None

    def run(self, epoch_list, telescope_list):
        for epoch, telescope in itertools.product(epoch_list, telescope_list):
            make_output_directory(self.processed_path, epoch, telescope)
            image_sets, image_configs = self.select_input_images(telescope, epoch)

            for image_set, image_config in zip(image_sets, image_configs):

                tags = logs.image_config_to_tags(image_config, telescope, epoch, self.group_by)
                self.logger.info(self.log_message, extra=tags)

                stage_args = [image_set]

                output_images = self.get_output_images(telescope, epoch)
                if output_images is not None:
                    stage_args.append(output_images)

                master_cal_file = self.get_calibration_image(epoch, telescope, image_config)
                if master_cal_file is not None:
                    stage_args.append(master_cal_file)

                self.do_stage(*stage_args)

    @abc.abstractmethod
    def do_stage(self, input_images):
        pass


class MakeCalibrationImage(Stage):
    def __init__(self, processed_path='', initial_query=None, group_by=None, logger_name='',
                 log_message='', cal_type='', previous_suffix_number='00', previous_stage_done=None):

        query = initial_query & (dbs.Image.obstype == cal_type)
        super(MakeCalibrationImage, self).__init__(processed_path=processed_path,
                                                   initial_query=query, group_by=group_by,
                                                   logger_name=logger_name, log_message=log_message, cal_type=cal_type,
                                                   previous_suffix_number=previous_suffix_number,
                                                   previous_stage_done=previous_stage_done)

    def get_calibration_image(self, epoch, telescope, image_config):
        output_directory = os.path.join(self.processed_path, telescope.site, telescope.instrument, epoch)
        cal_file = '{filepath}/{cal_type}_{instrument}_{epoch}_bin{bin}{filter}.fits'
        if dbs.Image.filter_name in self.group_by:
            filter_str = '_{filter}'.format(filter=image_config.filter_name)
        else:
            filter_str = ''

        cal_file = cal_file.format(filepath=output_directory, instrument=telescope.instrument, epoch=epoch,
                                   bin=image_config.ccdsum.replace(' ', 'x'), cal_type=self.cal_type, filter=filter_str)
        return cal_file

    def get_output_images(self, telescope, epoch):
        return None

    def save_calibration_info(self, cal_type, output_file, image_config):
        # Store the information into the calibration table
        # Check and see if the bias file is already in the database
        db_session = dbs.get_session()
        image_query = db_session.query(dbs.CalibrationImage)
        output_filename = os.path.basename(output_file)
        image_query = image_query.filter(dbs.CalibrationImage.filename == output_filename)
        image_query = image_query.all()

        if len(image_query) == 0:
            # Create a new row
            calibration_image = dbs.CalibrationImage()
        else:
            # Otherwise update the existing data
            # In principle we could just skip this, but this should be fast
            calibration_image = image_query[0]

        calibration_image.dayobs = image_config.dayobs
        calibration_image.ccdsum = image_config.ccdsum
        calibration_image.filter_name = image_config.filter_name
        calibration_image.telescope_id = image_config.telescope_id
        calibration_image.type = cal_type.upper()
        calibration_image.filename = output_filename
        calibration_image.filepath = os.path.dirname(output_file)

        db_session.add(calibration_image)
        db_session.commit()
        db_session.close()


class ApplyCalibration(Stage):
    def __init__(self, processed_path='', initial_query=None, group_by=None,
                 logger_name='', log_message='', cal_type='', db_session=None, image_suffix_number='00',
                 previous_suffix_number='00', previous_stage_done=None):
        super(ApplyCalibration, self).__init__(processed_path=processed_path,
                                               initial_query=initial_query, group_by=group_by, logger_name=logger_name,
                                               log_message=log_message, cal_type=cal_type,
                                               image_suffix_number=image_suffix_number,
                                               previous_suffix_number=previous_suffix_number,
                                               previous_stage_done=previous_stage_done)

    def get_output_images(self, telescope, epoch):
        image_sets, image_configs = self.select_input_images(telescope, epoch)
        return [image for image_set in image_sets for image in image_set]

    def get_calibration_image(self, epoch, telescope, image_config):
        calibration_criteria = dbs.CalibrationImage.type == self.cal_type.upper()
        calibration_criteria &= dbs.CalibrationImage.telescope_id == telescope.id

        for criteria in self.group_by:
            group_by_field = vars(criteria)['key']
            calibration_criteria &= getattr(dbs.CalibrationImage, group_by_field) == getattr(image_config,
                                                                                             group_by_field)

        db_session = dbs.get_session()

        calibration_query = db_session.query(dbs.CalibrationImage).filter(calibration_criteria)
        epoch_datetime = date_utils.epoch_string_to_date(epoch)

        find_closest = func.DATEDIFF(epoch_datetime, dbs.CalibrationImage.dayobs)
        find_closest = func.ABS(find_closest)

        calibration_query = calibration_query.order_by(find_closest.asc())
        calibration_image = calibration_query.first()
        calibration_file = os.path.join(calibration_image.filepath, calibration_image.filename)

        return calibration_file

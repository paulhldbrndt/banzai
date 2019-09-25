import pytest
import numpy as np
# from astropy.table import Table
from astropy.io import fits

# from banzai.images import Image, DataTable, regenerate_data_table_from_fits_hdu_list
# from banzai.tests.utils import FakeContext, FakeImage

from banzai.images import CCDData, LCOObservationFrame
from banzai.tests.utils import FakeCCDData, FakeLCOObservationFrame, FakeContext


# @pytest.fixture(scope='module')
# def set_random_seed():
#     np.random.seed(10031312)


def test_to_fits():
    test_data = FakeCCDData(meta={'EXTNAME': 'SCI'})
    hdu_list = test_data.to_fits()
    
    assert len(hdu_list) == 3
    assert hdu_list[0].header['EXTNAME'] == 'SCI'
    assert hdu_list[1].header['EXTNAME'] == 'BPM'
    assert hdu_list[2].header['EXTNAME'] == 'ERR'


def test_subtract():
    test_data = FakeCCDData(image_multiplier=4, uncertainty=3)
    test_data.subtract(1, uncertainty=4)

    assert (test_data.data == 3 * np.ones(test_data.data.shape)).all()
    assert test_data.uncertainty == 5


def test_trim():
    test_data = FakeCCDData(nx=1000, ny=1000, meta={'TRIMSEC': '[1:950, 1:945]'})
    test_data.trim()

    assert test_data.data.shape == (945, 950)
    assert test_data.mask.shape == (945, 950)
    assert test_data.uncertainty.shape == (945, 950)


def test_init_poisson_uncertainties():
    test_data = FakeCCDData(image_multiplier=4, uncertainty=1)
    test_data.init_poisson_uncertainties()

    assert (test_data.uncertainty == 3 * np.ones(test_data.data.shape)).all() 


def test_get_output_filename():
    test_frame = FakeLCOObservationFrame(file_path='test_image_00.fits')
    test_context = FakeContext(frame_class=FakeLCOObservationFrame)
    filename = test_frame.get_output_filename(test_context)

    assert filename == '/tmp/cpt/fa16/20160101/processed/test_image_91.fits.fz'


def test_get_mosaic_size():
    detsecs = [['[1:100,1:100]', '[1:100,200:101]', '[200:101,1:100]', '[200:101,200:101]'],
            ['[1:200,400:201]', '[1:200,1:200]', '[400:201,400:201]', '[400:201,1:200]'],
            ['[600:301,600:301]', '[600:301,1:300]', '[1:300,1:300]', '[1:300,600:301]'],
            ['[800:401,1:400]', '[800:401,800:401]', '[1:400,800:401]', '[1:400,1:400]'],
            ['[800:401,1:400]', None, '[1:400,800:401]', '[1:400,1:400]']]
    expected_mosaic_sizes = [(200, 200), (400, 400), (600, 600), (800, 800), (800, 800)]

    for idx, detsec in enumerate(detsecs):
        test_data = [FakeCCDData(meta={'CCDSUM': '1 1', 'DETSEC': detsec[amp]}) for amp in range(0, len(detsec))]
        test_frame = FakeLCOObservationFrame(hdu_list=test_data)
        assert test_frame.get_mosaic_size() == expected_mosaic_sizes[idx]


# def test_null_filename():
#     test_image = Image(FakeContext(), filename=None)
#     assert test_image.data is None


# def test_3d_is_3d():
#     test_image = FakeImage(n_amps=4)
#     assert test_image.data_is_3d()


# def test_2d_is_not_3d():
#     test_image = FakeImage()
#     assert not test_image.data_is_3d()


# def test_get_n_amps_3d():
#     test_image = FakeImage()
#     assert test_image.get_n_amps() == 1


# def test_get_n_amps_2d():
#     n_amps = 4
#     test_image = FakeImage(n_amps=n_amps)
#     assert test_image.get_n_amps() == n_amps


# def test_get_inner_quarter_default():
#     test_image = FakeImage()
#     test_image.data = np.random.randint(0, 1000, size=test_image.data.shape)
#     # get inner quarter manually
#     inner_nx = round(test_image.nx * 0.25)
#     inner_ny = round(test_image.ny * 0.25)
#     inner_quarter = test_image.data[inner_ny:-inner_ny, inner_nx:-inner_nx]
#     np.testing.assert_array_equal(test_image.get_inner_image_section(), inner_quarter)


# def test_get_inner_image_section_3d():
#     test_image = FakeImage(n_amps=4)
#     with pytest.raises(ValueError):
#         test_image.get_inner_image_section()


# def test_image_creates_and_loads_tables_correctly():
#     """
#     Tests that add_data_tables_to_hdu_list and regenerate_data_table_from_fits_hdu_list
#     create fits.HDUList objects correctly from astropy tables with single element entries
#     and for astropy tables with columns where each element is a list.
#     """
#     test_image = Image(FakeContext(), filename=None)
#     table_name = 'test'
#     a = np.arange(3)
#     array_1 = [a, a]
#     array_2 = [a, np.vstack((a, a)).T]
#     for test_array in [array_1, array_2]:
#         test_table = Table(test_array, names=('1', '2'), meta={'name': table_name})
#         test_table['1'].description = 'test_description'
#         test_table['1'].unit = 'pixel'
#         test_image.data_tables[table_name] = DataTable(data_table=test_table, name=table_name)
#         hdu_list = []
#         hdu_list = test_image._add_data_tables_to_hdu_list(hdu_list)
#         fits_hdu_list = fits.HDUList(hdu_list)
#         test_table_dict = regenerate_data_table_from_fits_hdu_list(fits_hdu_list, table_extension_name=table_name)
#         test_table_recreated = test_table_dict[table_name]
#         assert (test_table_recreated == test_table).all()


# def test_data_table_adds_columns():
#     fake_table = Table([[1, 2.5]], names=('a',))
#     data_table = DataTable(fake_table, name='test')
#     data_table.add_column(np.arange(2), name='b', index=0)
#     assert np.allclose(data_table['b'], np.arange(2))
#     data_table.add_column(np.arange(1, 3), name='c', index=1)
#     assert np.allclose(data_table['c'], np.arange(1, 3))

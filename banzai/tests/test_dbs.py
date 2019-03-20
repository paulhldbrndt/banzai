import os

import mock

from banzai import dbs
from banzai.tests.utils import FakeResponse


@mock.patch('banzai.dbs.requests.get', return_value=FakeResponse())
def setup_module(mockrequests):
    dbs.create_db('.', db_address='sqlite:///test.db')


def teardown_module():
    os.remove('test.db')


def test_add_or_update():
    db_session = dbs.get_session(db_address='sqlite:///test.db')
    # Add a fake telescope
    dbs.add_or_update_record(db_session, dbs.Instrument, {'site': 'bpl', 'camera': 'kb101', 'enclosure': 'doma',
                                                          'telescope': '1m0a'},
                             {'site': 'bpl', 'camera': 'kb101', 'enclosure': 'doma', 'telescope': '1m0a',
                              'type': 'SBig', 'schedulable': False})
    db_session.commit()

    # Make sure it got added
    query = db_session.query(dbs.Instrument).filter(dbs.Instrument.site == 'bpl')
    telescope = query.filter(dbs.Instrument.camera == 'kb101').first()
    assert telescope is not None

    # Update the fake telescope
    dbs.add_or_update_record(db_session, dbs.Instrument, {'site': 'bpl', 'camera': 'kb101', 'enclosure': 'doma',
                                                          'telescope': '1m0a'},
                             {'site': 'bpl', 'camera': 'kb101', 'enclosure': 'doma', 'telescope': '1m0a',
                              'type': 'SBig', 'schedulable': True})

    db_session.commit()
    # Make sure the update took
    query = db_session.query(dbs.Instrument).filter(dbs.Instrument.site == 'bpl')
    telescope = query.filter(dbs.Instrument.camera == 'kb101').first()
    assert telescope is not None
    assert telescope.schedulable

    # make sure there is only one new telescope in the table
    query = db_session.query(dbs.Instrument).filter(dbs.Instrument.site == 'bpl')
    telescopes = query.filter(dbs.Instrument.camera == 'kb101').all()
    assert len(telescopes) == 1

    # Clean up for other methods
    db_session.delete(telescope)
    db_session.commit()
    db_session.close()


def test_removing_duplicates():
    nres_inst = {'site': 'tlv', 'camera': 'nres01', 'schedulable': True}
    other_inst = {'site': 'tlv', 'camera': 'cam01', 'schedulable': True}
    instruments = [other_inst] + [nres_inst]*3
    culled_list = dbs.remove_nres_duplicates(instruments)
    assert len(culled_list) == 2
    assert culled_list[1]['camera'] == 'nres01'
    assert culled_list[0]['camera'] == 'cam01'


def test_removing_duplicates_favors_scheduluable():
    nres_inst = {'site': 'tlv', 'camera': 'nres01', 'schedulable': True}
    other_inst = {'site': 'tlv', 'camera': 'cam01', 'schedulable': True}
    instruments = [other_inst, nres_inst, {'site': 'tlv', 'camera': 'nres01', 'schedulable': False}]
    culled_list = dbs.remove_nres_duplicates(instruments)
    assert len(culled_list) == 2
    assert culled_list[1]['camera'] == 'nres01'
    assert culled_list[0]['camera'] == 'cam01'
    assert culled_list[1]['schedulable']


def test_not_removing_singlets():
    nres_inst = {'site': 'tlv', 'camera': 'nres01', 'schedulable': True}
    other_inst = {'site': 'tlv', 'camera': 'cam01', 'schedulable': True}
    instruments = [other_inst] + [nres_inst]
    culled_list = dbs.remove_nres_duplicates(instruments)
    assert len(culled_list) == 2
    assert culled_list[1]['camera'] == 'nres01'
    assert culled_list[0]['camera'] == 'cam01'

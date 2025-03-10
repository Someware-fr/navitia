# Copyright (c) 2001-2022, Hove and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Hove (www.hove.com).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# channel `#navitia` on riot https://riot.im/app/#/room/#navitia:matrix.org
# https://groups.google.com/d/forum/navitia
# www.navitia.io

from __future__ import absolute_import, print_function, unicode_literals, division

import copy

import navitiacommon.response_pb2 as response_pb2
import navitiacommon.type_pb2 as type_pb2
import jormungandr.scenarios.tests.helpers_tests as helpers_tests
from jormungandr.scenarios import new_default, journey_filter
from jormungandr.scenarios.new_default import (
    _tag_journey_by_mode,
    get_kraken_calls,
    update_best_boarding_positions,
    add_olympics_forbidden_uris,
    apply_origin_destination_rules,
    tag_special_event,
    SPECIAL_EVENT,
)
from jormungandr.instance import Instance
from jormungandr.scenarios.utils import switch_back_to_ridesharing
from jormungandr.utils import make_origin_destination_key, str_to_time_stamp
from werkzeug.exceptions import HTTPException
import pytest
from collections import defaultdict

"""
 sections       0   1   2   3   4   5   6   7   8   9   10
 -------------------------------------------------------------
JOURNEYS 1          1   1   1   1                       1    |
JOURNEYS 2          1   1           1   1               1    |
JOURNEYS 3              1   1   1                       1    |
JOURNEYS 4              1           1   1               1    |
JOURNEYS 5      1       1   1           1               1    |
JOURNEYS 6          1   1                    1          1    |
JOURNEYS 7          1   1                        1      1    |
JOURNEYS 8              1                    1          1    |
JOURNEYS 9              1                        1      1    |
JOURNEYS 10     1       1                    1          1    |
JOURNEYS 11         1   1                        1  1        |
JOURNEYS 12             1                        1  1        |
JOURNEYS 13     1       1                        1  1        |
JOURNEYS 14     1                                   1        |
JOURNEYS 15     1                                1  1        |
JOURNEYS 16     1                                            |
JOURNEYS 17                                             1    |
JOURNEYS 18     1                                1  1        | -> same as J15 but arrive later
JOURNEYS 19              1   1   1                       1   | -> same as J3 but arrive later
"""
SECTIONS_CHOICES = (
    (response_pb2.STREET_NETWORK, response_pb2.Bike, 'bike'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_1'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_2'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_3'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_4'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_5'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_6'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_7'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_8'),
    (response_pb2.PUBLIC_TRANSPORT, None, 'uri_9'),
    (response_pb2.STREET_NETWORK, response_pb2.Walking, 'walking'),
)

JOURNEYS = (
    # J1
    # 10/15/2015 @ 12:30pm (UTC)
    (1444905000, 'rapid', (1, 2, 3, 4, 10)),
    # J2
    # 10/15/2015 @ 12:35pm (UTC)
    (1444905300, 'rapid', (1, 2, 5, 6, 10)),
    # J3
    # 10/15/2015 @ 12:40pm (UTC)
    (1444905600, 'rapid', (2, 3, 4, 10)),
    # J4
    # 10/15/2015 @ 12:45pm (UTC)
    (1444905900, 'rapid', (2, 5, 6, 10)),
    # J5
    # 10/15/2015 @ 12:50pm (UTC)
    (1444906200, 'rapid', (0, 2, 3, 6, 10)),
    # J6
    # 10/15/2015 @ 12:55pm (UTC)
    (1444906500, 'rapid', (1, 2, 7, 10)),
    # J7
    # 10/15/2015 @ 13:00pm (UTC)
    (1444906800, 'rapid', (1, 2, 8, 10)),
    # J8
    # 10/15/2015 @ 13:05pm (UTC)
    (1444907100, 'rapid', (2, 7, 10)),
    # J9
    # 10/15/2015 @ 13:10pm (UTC)
    (1444907400, 'rapid', (2, 8, 10)),
    # J10
    # 10/15/2015 @ 13:15pm (UTC)
    (1444907700, 'rapid', (0, 2, 7, 10)),
    # J11
    # 10/15/2015 @ 13:20pm (UTC)
    (1444908800, 'rapid', (1, 2, 8, 9)),
    # J12
    # 10/15/2015 @ 13:25pm (UTC)
    (1444909100, 'rapid', (2, 8, 9)),
    # J13
    # 10/15/2015 @ 13:30pm (UTC)
    (1444909400, 'rapid', (0, 2, 8, 9)),
    # J14
    # 10/15/2015 @ 12:30pm (UTC)
    (1444905000, 'comfort', (0, 9)),
    # J15
    # 10/15/2015 @ 12:08pm (UTC)
    (1444903680, 'best', (0, 8, 9)),
    # J16
    # 10/15/2015 @ 12:08pm (UTC)
    (1444903680, 'non_pt_bike', (0,)),
    # J17
    # 10/15/2015 @ 12:05pm (UTC)
    (1444903500, 'non_pt_walk', (10,)),
    # J18 -> same as J15 but arrive later than J15
    # 10/15/2015 @ 12:10pm (UTC)
    (1444903800, 'rapid', (0, 8, 9)),
    # J19 -> same as J3 but arrive later than J3
    # 10/15/2015 @ 12:42pm (UTC)
    (1444905720, 'rapid', (2, 3, 4, 10)),
)


def build_mocked_response():
    response = response_pb2.Response()
    for jrny in JOURNEYS:
        arrival_time, jrny_type, sections_idx = jrny
        pb_j = response.journeys.add()
        pb_j.arrival_date_time = arrival_time
        # we remove the street network section
        pb_j.nb_transfers = len(sections_idx) - 1 - (1 in sections_idx) - (10 in sections_idx)
        if jrny_type:
            pb_j.type = jrny_type
        for idx in sections_idx:
            section_type, network_mode, line_uri = SECTIONS_CHOICES[idx]
            section = pb_j.sections.add()
            section.type = section_type
            if network_mode:
                section.street_network.mode = network_mode
            if line_uri:
                section.uris.line = line_uri

    new_default._tag_by_mode([response])
    new_default._tag_direct_path([response])
    new_default._tag_bike_in_pt([response])

    return response


def create_candidate_pool_and_sections_set_test():
    """
    Given response, the tested function should return a candidate pool and a section set
    """
    mocked_pb_response = build_mocked_response()
    candidates_pool, sections_set, idx_jrny_must_keep = new_default._build_candidate_pool_and_sections_set(
        mocked_pb_response.journeys
    )

    # We got 19 journeys in all and 4 of them are tagged with 'best', 'comfort', 'non_pt_bike', 'non_pt_walk'
    assert candidates_pool.shape[0] == 19
    assert len(idx_jrny_must_keep) == 4

    assert len(sections_set) == 11


def build_candidate_pool_and_sections_set_test():
    mocked_pb_response = build_mocked_response()
    candidates_pool, sections_set, idx_jrny_must_keep = new_default._build_candidate_pool_and_sections_set(
        mocked_pb_response.journeys
    )
    selected_sections_matrix = new_default._build_selected_sections_matrix(sections_set, candidates_pool)

    # selected_sections_matrix should have 19 lines(19 journeys) and 11 columns(11 sections)
    assert selected_sections_matrix.shape == (19, 11)

    # it's too verbose to check the entire matrix... we check only two lines
    assert [1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1] in selected_sections_matrix
    assert [0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1] in selected_sections_matrix


def get_sorted_solutions_indexes_test():
    mocked_pb_response = build_mocked_response()
    candidates_pool, sections_set, idx_jrny_must_keep = new_default._build_candidate_pool_and_sections_set(
        mocked_pb_response.journeys
    )
    selected_sections_matrix = new_default._build_selected_sections_matrix(sections_set, candidates_pool)
    # 4 journeys are must-have, we'd like to select another 5 journeys
    best_indexes, selection_matrix = new_default._get_sorted_solutions_indexes(
        selected_sections_matrix, (5 + 4), idx_jrny_must_keep
    )

    assert best_indexes.shape[0] == 33
    assert all(selection_matrix[best_indexes[0]] == [0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0])


def culling_journeys_1_test():
    """
    Test when max_nb_journeys is bigger than journey's length in response,
    none of journeys are cut out
    """
    mocked_pb_response = build_mocked_response()
    nb_journeys = len(mocked_pb_response.journeys)
    mocked_request = {'max_nb_journeys': nb_journeys + 1, 'debug': False}
    new_default.culling_journeys(mocked_pb_response, mocked_request)
    assert len(mocked_pb_response.journeys) == nb_journeys


def culling_journeys_2_test():
    """
    max_nb_journeys equals to nb of must-keep journeys ('comfort', 'best')
    """
    mocked_pb_response = build_mocked_response()
    mocked_request = {'max_nb_journeys': 2, 'debug': False}
    new_default.culling_journeys(mocked_pb_response, mocked_request)
    assert len(mocked_pb_response.journeys) == 2
    assert all([j.type in new_default.JOURNEY_TYPES_TO_RETAIN for j in mocked_pb_response.journeys])


def culling_journeys_2_bis_test():
    """
    max_nb_journeys equals to nb of must-keep journeys ('comfort', 'best', 'non_pt_bike', 'non_pt_walk')
    Here we test the case where max_nb_journeys equals to nb_journeys_must_have
    """
    mocked_pb_response = build_mocked_response()
    mocked_request = {'max_nb_journeys': 4, 'debug': False}
    new_default.culling_journeys(mocked_pb_response, mocked_request)
    assert len(mocked_pb_response.journeys) == 4
    assert all([j.type in new_default.JOURNEY_TYPES_TO_RETAIN for j in mocked_pb_response.journeys])


def culling_journeys_3_test():
    mocked_pb_response = build_mocked_response()
    mocked_request = {'max_nb_journeys': 6, 'debug': False, 'datetime': 1444903200}
    new_default.culling_journeys(mocked_pb_response, mocked_request)
    assert len(mocked_pb_response.journeys) == 6

    journey_uris = {
        ((u'uri_1', u'uri_2', u'uri_5', u'uri_6', u'walking'), 1444905300),
        ((u'uri_2', u'uri_3', u'uri_4', u'walking'), 1444905600),
        ((u'bike', u'uri_2', u'uri_7', u'walking'), 1444907700),
        ((u'bike', u'uri_9'), 1444905000),
        ((u'bike', u'uri_8', u'uri_9'), 1444903680),
        ((u'bike',), 1444903680),
        ((u'walking',), 1444903500),
    }
    for j in mocked_pb_response.journeys:
        assert (tuple(s.uris.line for s in j.sections), j.arrival_date_time) in journey_uris


def culling_journeys_4_test():
    """
    When max_nb_journeys == 3 and nb_must_have_journeys == 4
    """
    mocked_pb_response = build_mocked_response()
    mocked_request = {'max_nb_journeys': 3, 'debug': False, 'datetime': 1444903200}
    new_default.culling_journeys(mocked_pb_response, mocked_request)
    assert len(mocked_pb_response.journeys) == 3
    for jrny in mocked_pb_response.journeys:
        # 'non_pt_bike' shouldn't appear in returned journeys
        assert jrny.type in ('best', 'comfort', 'non_pt_walk')


def aggregate_journeys_test():
    mocked_pb_response = build_mocked_response()
    aggregated_journeys, remaining_journeys = new_default.aggregate_journeys(mocked_pb_response.journeys)
    assert len(aggregated_journeys) == 17
    assert len(remaining_journeys) == 2


def merge_responses_on_errors_test():
    """
    check the merge responses when several errors are provided
    """
    resp1 = response_pb2.Response()
    resp1.error.id = response_pb2.Error.date_out_of_bounds
    resp1.error.message = "you're out of the bound"
    resp2 = response_pb2.Response()
    resp2.error.id = response_pb2.Error.bad_format
    resp2.error.message = "you've been bad"
    r = [resp1, resp2]

    merged_response = new_default.merge_responses(r, False)

    assert merged_response.HasField(str('error'))
    assert merged_response.error.id == response_pb2.Error.no_solution
    # both messages must be in the composite error
    assert resp1.error.message in merged_response.error.message
    assert resp2.error.message in merged_response.error.message


def merge_responses_feed_publishers_test():
    """
    Check that the feed publishers are exposed according to the itineraries
    """
    resp1 = response_pb2.Response()
    fp1 = resp1.feed_publishers.add()
    fp1.id = "Bobby"
    j1 = resp1.journeys.add()
    resp2 = response_pb2.Response()
    fp2 = resp2.feed_publishers.add()
    fp2.id = "Bobbette"
    j2 = resp2.journeys.add()
    r = [resp1, resp2]

    # The feed publishers of both journeys are exposed
    merged_response = new_default.merge_responses(r, False)
    assert len(merged_response.feed_publishers) == 2

    # The 2nd journey is to be deleted, the feed publisher should still be exposed
    resp2.journeys.add().tags.extend(['to_delete'])
    merged_response = new_default.merge_responses(r, False)
    assert len(merged_response.feed_publishers) == 2
    assert merged_response.feed_publishers[0].id == 'Bobby'

    # All journeys are tagged as 'to_delete', no feed publishers should be exposed
    j1.tags.extend(['to_delete'])
    j2.tags.extend(['to_delete'])
    merged_response = new_default.merge_responses([resp1, resp2], False)
    assert len(merged_response.feed_publishers) == 0

    # With 'debug=True', the journey to delete is exposed and so is its feed publisher
    merged_response = new_default.merge_responses(r, True)
    assert len(merged_response.feed_publishers) == 2


def get_kraken_calls_test():
    for md in ["bike", "walking", "bss", "car", "ridesharing", "taxi"]:
        req = {"origin_mode": [md], "destination_mode": [md]}
        assert get_kraken_calls(req) == {(md, md, "indifferent")}

    req = {"origin_mode": ["bss", "walking"], "destination_mode": ["walking"], "direct_path": "none"}
    assert get_kraken_calls(req) == {("walking", "walking", "none")}

    req = {"origin_mode": ["bike", "walking"], "destination_mode": ["walking"], "direct_path": "indifferent"}
    assert get_kraken_calls(req) == {("walking", "walking", "indifferent"), ("bike", "walking", "indifferent")}

    req = {"origin_mode": ["bike", "walking"], "destination_mode": ["bss"], "direct_path": "indifferent"}
    assert get_kraken_calls(req) == {("bike", "bss", "indifferent")}

    req = {"origin_mode": ["bike", "car"], "destination_mode": ["bss"]}
    assert get_kraken_calls(req) == {("bike", "bss", "indifferent"), ("car", "bss", "indifferent")}

    req = {"origin_mode": ["bss", "bike"], "destination_mode": ["bike"]}
    assert get_kraken_calls(req) == {("bike", "bike", "indifferent")}

    req = {"origin_mode": ["taxi", "bike"], "destination_mode": ["walking", "bss", "car", "ridesharing", "taxi"]}
    assert get_kraken_calls(req) == {
        ('taxi', 'taxi', "indifferent"),
        ('taxi', 'bss', "indifferent"),
        ('bike', 'bss', "indifferent"),
        ('bike', 'walking', "indifferent"),
        ('bike', 'taxi', "indifferent"),
        ('taxi', 'walking', "indifferent"),
        ('taxi', 'ridesharing', "indifferent"),
    }

    req = {
        "origin_mode": ["ridesharing", "taxi"],
        "destination_mode": ["walking", "bss", "bike", "car", "ridesharing", "taxi"],
    }
    assert get_kraken_calls(req) == {
        ('taxi', 'taxi', "indifferent"),
        ('ridesharing', 'walking', "indifferent"),
        ('taxi', 'bss', "indifferent"),
        ('ridesharing', 'bss', "indifferent"),
        ('taxi', 'ridesharing', "indifferent"),
        ('taxi', 'walking', "indifferent"),
        ('ridesharing', 'taxi', "indifferent"),
    }

    req = {"origin_mode": ["bss", "walking"], "destination_mode": ["walking"], "direct_path_mode": ["walking"]}
    assert get_kraken_calls(req) == {("walking", "walking", "indifferent")}

    req = {"origin_mode": ["bss", "walking"], "destination_mode": ["walking"], "direct_path_mode": ["bike"]}
    assert get_kraken_calls(req) == {("walking", "walking", "indifferent"), ("bike", "bike", "only")}

    req = {
        "origin_mode": ["bss", "walking"],
        "destination_mode": ["walking"],
        "direct_path_mode": ["bike"],
        "direct_path": "none",
    }
    assert get_kraken_calls(req) == {("walking", "walking", "none")}

    req = {
        "origin_mode": ["walking"],
        "destination_mode": ["walking"],
        "direct_path_mode": ["bike", "car"],
        "direct_path": "only",
    }
    assert get_kraken_calls(req) == {("bike", "bike", "only"), ("car", "car", "only")}

    req = {
        "origin_mode": ["walking"],
        "destination_mode": ["walking"],
        "direct_path_mode": ["bike", "car"],
        "direct_path": "only_with_alternatives",
    }
    assert get_kraken_calls(req) == {("bike", "bike", "only"), ("car", "car", "only")}

    req = {
        "origin_mode": [],
        "destination_mode": [],
        "direct_path_mode": ["bike"],
        "direct_path": "only",
    }
    assert get_kraken_calls(req) == {("bike", "bike", "only")}

    req = {
        "origin_mode": [],
        "destination_mode": [],
        "direct_path_mode": ["bike"],
        "direct_path": "only_with_alternatives",
    }
    assert get_kraken_calls(req) == {("bike", "bike", "only")}

    req = {
        "origin_mode": ["walking", "bike"],
        "destination_mode": ["walking"],
        "direct_path_mode": [],
        "direct_path": "only",
    }
    assert get_kraken_calls(req) == {("walking", "walking", "only"), ("bike", "walking", "only")}


def get_kraken_calls_invalid_1_test():
    with pytest.raises(HTTPException):
        get_kraken_calls({"origin_mode": ["bss", "walking"], "destination_mode": ["car"]})


def get_kraken_calls_invalid_2_test():
    with pytest.raises(HTTPException):
        get_kraken_calls({"origin_mode": ["bss", "walking"], "destination_mode": ["bike"]})


def tag_by_mode_test():
    ww = helpers_tests.get_walking_walking_journey()
    _tag_journey_by_mode(ww)
    assert 'walking' in ww.tags
    wb = helpers_tests.get_walking_bike_journey()
    _tag_journey_by_mode(wb)
    assert 'bike' in wb.tags
    wbss = helpers_tests.get_walking_bss_journey()
    _tag_journey_by_mode(wbss)
    assert 'bss' in wbss.tags
    wc = helpers_tests.get_walking_car_journey()
    _tag_journey_by_mode(wc)
    assert 'car' in wc.tags
    cw = helpers_tests.get_car_walking_journey()
    _tag_journey_by_mode(cw)
    assert 'car' in cw.tags
    c = helpers_tests.get_car_journey()
    _tag_journey_by_mode(c)
    assert 'car' in c.tags
    bw = helpers_tests.get_bike_walking_journey()
    _tag_journey_by_mode(bw)
    assert 'bike' in bw.tags
    bbss = helpers_tests.get_bike_bss_journey()
    _tag_journey_by_mode(bbss)
    assert 'bike' in bbss.tags
    bc = helpers_tests.get_bike_car_journey()
    _tag_journey_by_mode(bc)
    assert 'car' in bc.tags
    bw = helpers_tests.get_bike_walking_journey()
    _tag_journey_by_mode(bw)
    assert 'bike' in bw.tags
    bssb = helpers_tests.get_bss_bike_journey()
    _tag_journey_by_mode(bssb)
    assert 'bike' in bssb.tags
    bssbss = helpers_tests.get_bss_bss_journey()
    _tag_journey_by_mode(bssbss)
    assert 'bss' in bssbss.tags
    bssc = helpers_tests.get_bss_car_journey()
    _tag_journey_by_mode(bssc)
    assert 'car' in bssc.tags
    bb = helpers_tests.get_bike_bike_journey()
    _tag_journey_by_mode(bb)
    assert 'bike' in bb.tags
    rs_car = helpers_tests.get_ridesharing_with_car_journey()
    _tag_journey_by_mode(rs_car)
    assert 'ridesharing' in rs_car.tags
    rs_crowfly = helpers_tests.get_ridesharing_with_crowfly_journey()
    _tag_journey_by_mode(rs_crowfly)
    assert 'ridesharing' in rs_crowfly.tags


def tag_direct_path_test():
    response = response_pb2.Response()

    # test with one walk and one pt
    journey_walk = response.journeys.add()
    section = journey_walk.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    journey_bike = response.journeys.add()
    section = journey_bike.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Bike
    journey_pt = response.journeys.add()
    section = journey_pt.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    new_default._tag_direct_path([response])
    assert 'non_pt_walking' in response.journeys[0].tags
    assert 'non_pt' in response.journeys[0].tags
    assert 'non_pt_bike' in response.journeys[1].tags
    assert 'non_pt' in response.journeys[1].tags
    assert not response.journeys[2].tags


def crowfly_in_ridesharing_test():
    response = response_pb2.Response()
    journey = response.journeys.add()

    section_crowfly = journey.sections.add()
    section_crowfly.type = response_pb2.CROW_FLY
    section_crowfly.street_network.mode = response_pb2.Car
    section_crowfly.duration = 42
    section_crowfly.length = 43

    journey.distances.car = 43
    journey.durations.car = 42
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking

    switch_back_to_ridesharing(response, True)

    assert section_crowfly.street_network.mode == response_pb2.Ridesharing
    assert journey.durations.ridesharing == 42
    assert journey.durations.car == 0
    assert journey.distances.ridesharing == 43
    assert journey.distances.car == 0


def filter_too_many_connections_test():
    # yes, it's a hack...
    instance = lambda: None

    instance.max_additional_connections = 10
    mocked_pb_response = build_mocked_response()
    mocked_request = {'debug': True, 'datetime': 1444903200, 'clockwise': True}
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    assert all('deleted_because_too_much_connections' not in j.tags for j in mocked_pb_response.journeys)

    instance.max_additional_connections = 0
    mocked_pb_response = build_mocked_response()
    mocked_request = {'debug': True, 'datetime': 1444903200, 'clockwise': True}
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    assert sum('deleted_because_too_much_connections' not in j.tags for j in mocked_pb_response.journeys) == 17
    # the best journey must be kept
    assert 'deleted_because_too_much_connections' not in mocked_pb_response.journeys[14].tags

    instance.max_additional_connections = 0
    mocked_pb_response = build_mocked_response()
    mocked_request = {'_max_additional_connections': 1, 'debug': True, 'datetime': 1444903200, 'clockwise': True}
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    assert sum('deleted_because_too_much_connections' not in j.tags for j in mocked_pb_response.journeys) == 19
    # the best journey must be kept
    assert 'deleted_because_too_much_connections' not in mocked_pb_response.journeys[14].tags


def build_mocked_car_response():
    response = response_pb2.Response()
    sections = (
        (response_pb2.STREET_NETWORK, response_pb2.Walking, 'walking'),
        (response_pb2.STREET_NETWORK, response_pb2.Car, 'car'),
        (response_pb2.PUBLIC_TRANSPORT, None, 'uri_1'),
        (response_pb2.PUBLIC_TRANSPORT, None, 'uri_2'),
    )
    journeys = (
        # J1
        # 10 / 15 / 2015 @ 12:30pm (UTC)
        # this journey will be tagged 'walking'
        (1444905000, 'rapid', (0, 2, 0)),
        # J2
        # 10 / 15 / 2015 @ 12:30pm (UTC)
        # this journey will be tagged 'car'
        (1444905000, 'car', (1, 3, 2)),
    )
    for jrny in journeys:
        arrival_time, jrny_type, sections_idx = jrny
        pb_j = response.journeys.add()
        pb_j.arrival_date_time = arrival_time
        # we remove the street network section
        pb_j.nb_transfers = len(sections_idx) - 1 - (1 in sections_idx) - (10 in sections_idx)
        if jrny_type:
            pb_j.type = jrny_type
        for idx in sections_idx:
            section_type, network_mode, line_uri = sections[idx]
            section = pb_j.sections.add()
            section.type = section_type
            if network_mode:
                section.street_network.mode = network_mode
            if line_uri:
                section.uris.line = line_uri

    new_default._tag_by_mode([response])
    new_default._tag_direct_path([response])
    new_default._tag_bike_in_pt([response])

    return response


def filter_non_car_tagged_journey_test():
    # yes, it's a hack...
    instance = lambda: None
    instance.max_additional_connections = 10

    mocked_pb_response = build_mocked_car_response()
    mocked_request = {'debug': True, 'datetime': 1444903200, 'clockwise': True}

    def expected_deleted_non_car_journey(journeys, nb):
        assert sum('deleted_because_non_car_tagged_journey_filtered' in j.tags for j in journeys) == nb

    expected_deleted_non_car_journey(mocked_pb_response.journeys, 0)

    # Apply filter
    # We should see no filtered journey because we did not request for first_section_mode/origin_mode = ['car'] only
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    expected_deleted_non_car_journey(mocked_pb_response.journeys, 0)

    # Apply filter
    # with origin_mode = ['car', 'walking'] the filter does not apply to our journeys
    mocked_request['origin_mode'] = ['car', 'walking']
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    expected_deleted_non_car_journey(mocked_pb_response.journeys, 0)

    # Apply filter
    # with origin_mode = ['car'] we expect to retain only 'car' tagged journey
    mocked_request['origin_mode'] = ['car']
    journey_filter.apply_final_journey_filters([mocked_pb_response], instance, mocked_request)
    expected_deleted_non_car_journey(mocked_pb_response.journeys, 1)


def build_response_with_transfer_and_vias():
    response = response_pb2.Response()
    journey = response.journeys.add()

    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Ridesharing
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section = journey.sections.add()
    section.type = response_pb2.TRANSFER
    section.origin.uri = 'stop_a'
    section.destination.uri = 'stop_b'
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'stop_x'
    via = section.vias.add()
    via.uri = 'stop_y'
    path_item = section.street_network.path_items.add()
    path_item.via_uri = 'stop_y'
    return response


def update_best_boarding_positions_test():
    def mock_get_best_boarding_position(from_id, to_id):
        my_key = make_origin_destination_key(from_id, to_id)
        return instance.best_boarding_positions.get(my_key, [])

    instance = lambda: None
    instance.best_boarding_positions = defaultdict(set)
    key = make_origin_destination_key('stop_a', 'stop_b')
    instance.best_boarding_positions[key].add(response_pb2.FRONT)
    key = make_origin_destination_key('stop_x', 'stop_y')
    instance.best_boarding_positions[key].add(response_pb2.MIDDLE)
    key = make_origin_destination_key('stop_x', 'stop_z')
    instance.best_boarding_positions[key].add(response_pb2.BACK)

    response = build_response_with_transfer_and_vias()
    instance.get_best_boarding_position = mock_get_best_boarding_position
    assert len(response.journeys) == 1
    journey = response.journeys[0]
    assert len(journey.sections) == 5
    assert journey.sections[1].type == response_pb2.PUBLIC_TRANSPORT
    assert not journey.sections[1].best_boarding_positions
    assert journey.sections[3].type == response_pb2.PUBLIC_TRANSPORT
    assert not journey.sections[3].best_boarding_positions
    update_best_boarding_positions(response, instance)
    # First PT section with ['FRONT'] calculated from the third section of type TRANSFER
    assert journey.sections[1].best_boarding_positions
    assert len(journey.sections[1].best_boarding_positions) == 1
    assert {response_pb2.BoardingPosition.FRONT} == set(iter(journey.sections[1].best_boarding_positions))
    # Second PT section with '['MIDDLE']' calculated from the last section of STREET_NETWORK with the via of the first path_item
    assert len(journey.sections[3].best_boarding_positions) == 1
    assert {response_pb2.BoardingPosition.MIDDLE} == set(iter(journey.sections[3].best_boarding_positions))


class FakeInstance:
    def __init__(self, name="fake_instance", criteria=None):
        self.name = name
        self.olympic_criteria = criteria


class FakeInstance(Instance):
    def __init__(self, name="fake_instance", olympics_forbidden_uris=None):
        super(FakeInstance, self).__init__(
            context=None,
            name=name,
            zmq_socket=None,
            street_network_configurations=[],
            ridesharing_configurations={},
            instance_equipment_providers=[],
            realtime_proxies_configuration=[],
            pt_planners_configurations={},
            zmq_socket_type=None,
            autocomplete_type='kraken',
            streetnetwork_backend_manager=None,
            external_service_provider_configurations=[],
            olympics_forbidden_uris=olympics_forbidden_uris,
        )


DEFAULT_OLYMPICS_FORBIDDEN_URIS = {
    "pt_object_olympics_forbidden_uris": ["nt:abc"],
    "poi_property_key": "olympic",
    "poi_property_value": "1234",
}


def make_pt_object_poi(property_type="olympic", property_value="1234"):
    pt_object_poi = type_pb2.PtObject()
    pt_object_poi.embedded_type = type_pb2.POI
    property = pt_object_poi.poi.properties.add()
    property.type = property_type
    property.value = property_value
    return pt_object_poi


def add_olympics_forbidden_uris_instance_without_criteria_test():
    api_request = {"param1": "toto"}
    origin = make_pt_object_poi()
    destination = make_pt_object_poi()
    instance = FakeInstance()
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" not in api_request


def add_olympics_forbidden_uris_instance_without_origin_test():
    api_request = {"param1": "toto"}
    origin = None
    destination = make_pt_object_poi()
    instance = FakeInstance(olympics_forbidden_uris=DEFAULT_OLYMPICS_FORBIDDEN_URIS)
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" not in api_request


def add_olympics_forbidden_uris_instance_without_destination_test():
    api_request = {"param1": "toto"}
    origin = make_pt_object_poi()
    destination = None
    instance = FakeInstance(olympics_forbidden_uris=DEFAULT_OLYMPICS_FORBIDDEN_URIS)
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" not in api_request


def add_olympics_forbidden_uris_instance_test():
    api_request = {"param1": "toto"}
    origin = make_pt_object_poi()
    destination = make_pt_object_poi()
    instance = FakeInstance(olympics_forbidden_uris=DEFAULT_OLYMPICS_FORBIDDEN_URIS)
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" not in api_request


def add_olympics_forbidden_uris_instance_query_with_forbidden_uris_without_min_pt_duration_test():
    api_request = {"param1": "toto", "forbidden_uris[]": ["abcd"]}
    origin = make_pt_object_poi(property_value="poi:12")
    destination = make_pt_object_poi(property_value="poi:12")
    instance = FakeInstance(olympics_forbidden_uris=DEFAULT_OLYMPICS_FORBIDDEN_URIS)
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" in api_request
    assert len(api_request["forbidden_uris[]"]) == 1
    assert api_request["forbidden_uris[]"][0] == "abcd"


def add_olympics_forbidden_uris_instance_query_with_forbidden_uris_test():
    api_request = {"param1": "toto", "forbidden_uris[]": ["abcd"]}
    origin = make_pt_object_poi(property_value="poi:12")
    destination = make_pt_object_poi(property_value="poi:12")
    olympics_forbidden_uris = copy.deepcopy(DEFAULT_OLYMPICS_FORBIDDEN_URIS)
    olympics_forbidden_uris["min_pt_duration"] = 5
    instance = FakeInstance(olympics_forbidden_uris=olympics_forbidden_uris)
    add_olympics_forbidden_uris(origin, destination, api_request, instance)
    assert "forbidden_uris[]" in api_request
    assert len(api_request["forbidden_uris[]"]) == 2
    assert api_request["forbidden_uris[]"][0] == "abcd"
    assert api_request["forbidden_uris[]"][1] == "nt:abc"


def add_olympics_forbidden_uris_invalid_parameter_test():
    instance = FakeInstance(olympics_forbidden_uris=[DEFAULT_OLYMPICS_FORBIDDEN_URIS])
    assert not instance.olympics_forbidden_uris


def add_olympics_forbidden_uris_without_pt_object_olympic_uris_test():
    olympics_forbidden_uris = {
        "poi_property_key": "olympic",
        "poi_property_value": "1234",
    }
    instance = FakeInstance(olympics_forbidden_uris=olympics_forbidden_uris)
    assert not instance.olympics_forbidden_uris


def add_olympics_forbidden_uris_without_poi_property_key_test():
    olympics_forbidden_uris = {
        "pt_object_olympics_forbidden_uris": ["nt:cc"],
        "forbidden_uris": ["nt:kk"],
        "poi_property_value": "1234",
    }
    instance = FakeInstance(olympics_forbidden_uris=olympics_forbidden_uris)
    assert not instance.olympics_forbidden_uris


def add_olympics_forbidden_uris_without_poi_property_value_test():
    olympics_forbidden_uris = {
        "pt_object_olympics_forbidden_uris": ["nt:cc"],
        "forbidden_uris": ["nt:kk"],
        "poi_property_key": "olympic",
    }
    instance = FakeInstance(olympics_forbidden_uris=olympics_forbidden_uris)
    assert not instance.olympics_forbidden_uris


def make_od_allowed_ids():
    my_dict = defaultdict(set)
    my_dict["sa:1-sa:10"] = ["rer:1", "bus:1", "metro:"]
    my_dict["sa:1-sa:11"] = ["train:2", "tram:2"]
    return my_dict


def test_od_allowed_ids_absent():
    api_request = {"param1": "toto", "datetime": str_to_time_stamp('20230813T150000')}

    origin_uri = "sa:1"
    destination_uri = "sa:10"
    instance = FakeInstance()
    instance.od_allowed_ids = None
    apply_origin_destination_rules(origin_uri, destination_uri, api_request, instance)
    assert "allowed_id[]" not in api_request


def test_od_allowed_ids_present_but_od_absent():
    api_request = {"param1": "toto", "datetime": str_to_time_stamp('20230813T150000')}
    origin_uri = "sa:1"
    destination_uri = "sa:toto"
    instance = FakeInstance()
    instance.od_allowed_ids = make_od_allowed_ids()
    apply_origin_destination_rules(origin_uri, destination_uri, api_request, instance)
    assert "allowed_id[]" not in api_request


def test_od_allowed_ids_present_and_od_present():
    api_request = {"param1": "toto", "datetime": str_to_time_stamp('20230813T150000')}
    origin_uri = "sa:1"
    destination_uri = "sa:10"
    instance = FakeInstance()
    instance.od_allowed_ids = make_od_allowed_ids()
    instance.additional_params_period_start = str_to_time_stamp('20230812T000000')
    instance.additional_params_period_end = str_to_time_stamp('20230814T215959')
    apply_origin_destination_rules(origin_uri, destination_uri, api_request, instance)
    assert "allowed_id[]" in api_request
    assert api_request["allowed_id[]"][0] == "rer:1"
    assert api_request["allowed_id[]"][1] == "bus:1"
    assert api_request["allowed_id[]"][2] == "metro:"

    # If request datetime is outside maintenance period, do not apply allowed_id
    api_request = {"param1": "toto", "datetime": str_to_time_stamp('20230810T100000')}
    apply_origin_destination_rules(origin_uri, destination_uri, api_request, instance)
    assert "allowed_id[]" not in api_request


def build_response_with_two_pt_ab_pq_and_street_network():
    # Journey One with StreetNetwork Walking + PT + Transfer + PT + StreetNetwork Walking
    #       |-------|--------------------|-----------------|------------|----------|
    # address_a   sa_a     PT          sa_b    MAP        sa_p   PT     sa_q   address_q
    response = response_pb2.Response()
    journey = response.journeys.add()
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'address_a'
    section.destination.uri = 'sp_a'
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_a'
    section.destination.stop_point.stop_area.uri = 'sa_b'
    section.uris.line = "rer:1"
    section = journey.sections.add()
    section.type = response_pb2.TRANSFER
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_p'
    section.destination.stop_point.stop_area.uri = 'sa_q'
    section.uris.line = "bus:1"
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'sp_q'
    section.destination.uri = 'address_q'
    return response


def build_response_with_two_pt_yx_ba_and_street_network():
    # Journey One with StreetNetwork Walking + PT + Transfer + PT + StreetNetwork Walking
    #       |-------|--------------------|-----------------|------------|----------|
    # address_y   sa_y     PT          sa_x    MAP        sa_b   PT     sa_a   address_a
    response = response_pb2.Response()
    journey = response.journeys.add()
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'address_y'
    section.destination.uri = 'sp_y'
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_y'
    section.destination.stop_point.stop_area.uri = 'sa_x'
    section.uris.line = "rer:xy"
    section = journey.sections.add()
    section.type = response_pb2.TRANSFER
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_b'
    section.destination.stop_point.stop_area.uri = 'sa_a'
    section.uris.line = "bus:1"
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'sp_a'
    section.destination.uri = 'address_a'
    return response


def build_response_with_two_pt_ab_xy_and_street_network():
    # Journey One with StreetNetwork Walking + PT + Transfer + PT + StreetNetwork Walking
    #       |-------|--------------------|-----------------|------------|----------|
    # address_a   sa_a     PT          sa_b    MAP        sa_x   PT     sa_y   address_y
    response = response_pb2.Response()
    journey = response.journeys.add()
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'address_a'
    section.destination.uri = 'sp_a'
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_a'
    section.destination.stop_point.stop_area.uri = 'sa_b'
    section.uris.line = "rer:1"
    section = journey.sections.add()
    section.type = response_pb2.TRANSFER
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_x'
    section.destination.stop_point.stop_area.uri = 'sa_y'
    section.uris.line = "bus:xy"
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'sp_y'
    section.destination.uri = 'address_y'
    return response


def build_response_with_one_pt_b_to_a_and_street_network():
    # Journey One with StreetNetwork Walking + PT + StreetNetwork Walking
    #       |-------|--------------------|-----------------|
    # address_b   sa_b     PT          sa_a    MAP        address_a
    response = response_pb2.Response()
    journey = response.journeys.add()
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'address_b'
    section.destination.uri = 'sp_b'
    section = journey.sections.add()
    section.type = response_pb2.PUBLIC_TRANSPORT
    section.origin.stop_point.stop_area.uri = 'sa_b'
    section.destination.stop_point.stop_area.uri = 'sa_a'
    section.uris.line = "rer:1"
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'sp_a'
    section.destination.uri = 'address_a'
    return response


def build_direct_path_response_with_walking():
    response = response_pb2.Response()
    # Journey One with only StreetNetwork Walking (direct_path)
    journey = response.journeys.add()
    section = journey.sections.add()
    section.type = response_pb2.STREET_NETWORK
    section.street_network.mode = response_pb2.Walking
    section.origin.uri = 'sa_b'
    section.destination.uri = 'sa_c'
    return response


def make_basic_od_allowed_ids():
    # Adding allowed_ids for stop_area_a, stop_area_c and stop_area_q
    my_dict = defaultdict(set)
    od_stop_areas = set()
    od_lines = set()
    my_dict["sa_a-sa_c"] = ["rer:1", "bus:1"]
    my_dict["sa_c-sa_a"] = ["rer:1", "bus:1"]
    my_dict["sa_a-sa_q"] = ["train:2", "tram:2"]
    my_dict["sa_q-sa_a"] = ["train:2", "tram:2"]
    od_stop_areas.add("sa_a")
    od_stop_areas.add("sa_c")
    od_stop_areas.add("sa_q")
    od_lines.add("rer:1")
    od_lines.add("bus:1")
    od_lines.add("train:2")
    od_lines.add("tram:2")
    return my_dict, od_stop_areas, od_lines


def make_od_additional_parameters():
    my_dict = defaultdict(set)
    my_dict["sa_b-sa_c"] = ["direct_path_mode[]=walking", "direct_path=only"]
    my_dict["sa_c-sa_b"] = ["direct_path_mode[]=walking", "direct_path=only"]
    return my_dict, None, None


def test_tag_special_event():
    instance = FakeInstance()

    # 1. A journey has only Walking section with origin and destination present in od_additional_parameters matrix:
    instance.od_additional_parameters, _, _ = make_od_additional_parameters()
    pb_resp = build_direct_path_response_with_walking()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT in pb_resp.journeys[0].tags

    # 2. All line uri are in od_lines and any origin or destination in od_stop_area
    # Journey has two PT sections, origin.stop_point.stop_area.uri (sa_a) of first PT section and
    # destination.stop_point.stop_area.uri ('sa_q') of last PT section are in od_stop_areas
    # line uri of both PT sections are in od_lines
    instance.od_allowed_ids, instance.od_stop_areas, instance.od_lines = make_basic_od_allowed_ids()
    pb_resp = build_response_with_two_pt_ab_pq_and_street_network()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT in pb_resp.journeys[0].tags

    # 3. line uri is in od_lines and destination uri is in od_stop_areas for at least one PT section
    # or
    # All line uri are in od_lines and any origin or destination in od_stop_area
    # Journey has one PT section, destination.stop_point.stop_area.uri ('sa_a') of PT section is in od_stop_areas
    # line uri ('rer:1') of the PT section is in od_lines
    instance.od_allowed_ids, instance.od_stop_areas, instance.od_lines = make_basic_od_allowed_ids()
    pb_resp = build_response_with_one_pt_b_to_a_and_street_network()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT in pb_resp.journeys[0].tags

    # 4. line uri is in od_lines and destination uri is in od_stop_areas for at least one PT section
    # Journey has two PT sections, line uri ('bus:1') is in od_lines and destination uri ('sa_a') is in od_stop_areas
    # for the last PT section
    instance.od_allowed_ids, instance.od_stop_areas, instance.od_lines = make_basic_od_allowed_ids()
    pb_resp = build_response_with_two_pt_yx_ba_and_street_network()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT in pb_resp.journeys[0].tags

    # Journey has two PT sections, line uri ('rer:1') is in od_lines but destination uri ('sa_b')
    # is not in od_stop_areas for the last PT section
    instance.od_allowed_ids, instance.od_stop_areas, instance.od_lines = make_basic_od_allowed_ids()
    pb_resp = build_response_with_two_pt_ab_xy_and_street_network()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT not in pb_resp.journeys[0].tags

    # If od_allowed_ids is empty or None
    instance.od_allowed_ids = None
    instance.od_stop_areas = None
    instance.od_lines = None
    pb_resp = build_response_with_two_pt_ab_pq_and_street_network()
    tag_special_event(instance, pb_resp)
    assert SPECIAL_EVENT not in pb_resp.journeys[0].tags

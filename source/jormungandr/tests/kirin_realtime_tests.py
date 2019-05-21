# Copyright (c) 2001-2015, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
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
# IRC #navitia on freenode
# https://groups.google.com/d/forum/navitia
# www.navitia.io

# Note: the tests_mechanism should be the first
# import for the conf to be loaded correctly when only this test is ran
from __future__ import absolute_import

from copy import deepcopy

from datetime import datetime
import uuid
from tests.tests_mechanism import dataset
from jormungandr.utils import str_to_time_stamp, make_namedtuple
from tests import gtfs_realtime_pb2, kirin_pb2
from tests.check_utils import (
    get_not_null,
    journey_basic_query,
    isochrone_basic_query,
    get_used_vj,
    get_arrivals,
    get_valid_time,
    is_valid_disruption,
    check_journey,
    Journey,
    Section,
    SectionStopDT,
    is_valid_graphical_isochrone,
    sub_query,
    has_the_disruption,
    get_disruptions_by_id,
)
from tests.rabbitmq_utils import RabbitMQCnxFixture, rt_topic
from shapely.geometry import asShape


UpdatedStopTime = make_namedtuple(
    'UpdatedStopTime',
    'stop_id',
    'arrival',
    'departure',
    arrival_delay=0,
    departure_delay=0,
    message=None,
    departure_skipped=False,
    arrival_skipped=False,
    is_added=False,
    is_detour=False,
)


class MockKirinDisruptionsFixture(RabbitMQCnxFixture):
    """
    Mock a chaos disruption message, in order to check the api
    """

    def _make_mock_item(self, *args, **kwargs):
        return make_mock_kirin_item(*args, **kwargs)


def tstamp(str):
    """just to have clearer tests"""
    return str_to_time_stamp(str)


def _dt(h, m, s):
    """syntaxic sugar"""
    return datetime(1900, 1, 1, hour=h, minute=m, second=s)


MAIN_ROUTING_TEST_SETTING = {
    'main_routing_test': {'kraken_args': ['--BROKER.rt_topics=' + rt_topic, 'spawn_maintenance_worker']}
}


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnVJDeletion(MockKirinDisruptionsFixture):
    def test_vj_deletion(self):
        """
        send a mock kirin vj cancellation and test that the vj is not taken
        """
        response = self.query_region(journey_basic_query + "&data_freshness=realtime")
        isochrone = self.query_region(isochrone_basic_query + "&data_freshness=realtime")

        # with no cancellation, we have 2 journeys, one direct and one with the vj:A:0
        assert get_arrivals(response) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(response) == [['vehicle_journey:vjA'], []]

        # Disruption impacting lines A, B, C starts at 06:00 and ends at 11:59:59
        # Get VJ at 12:00 and disruption doesn't appear
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T120000')
        assert len(pt_response['disruptions']) == 0

        is_valid_graphical_isochrone(isochrone, self.tester, isochrone_basic_query + "&data_freshness=realtime")
        geojson = isochrone['isochrones'][0]['geojson']
        multi_poly = asShape(geojson)

        # we have 3 departures and 1 disruption (linked to line A departure)
        departures = self.query_region("stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800")
        assert len(departures['disruptions']) == 1
        assert len(departures['departures']) == 3

        # A new disruption impacting vjA is created between 08:01:00 and 08:01:01
        self.send_mock("vjA", "20120614", 'canceled', disruption_id='disruption_bob')

        def _check_train_cancel_disruption(dis):
            is_valid_disruption(dis, chaos_disrup=False)
            assert dis['contributor'] == rt_topic
            assert dis['disruption_id'] == 'disruption_bob'
            assert dis['severity']['effect'] == 'NO_SERVICE'
            assert len(dis['impacted_objects']) == 1
            ptobj = dis['impacted_objects'][0]['pt_object']
            assert ptobj['embedded_type'] == 'trip'
            assert ptobj['id'] == 'vjA'
            assert ptobj['name'] == 'vjA'
            # for cancellation we do not output the impacted stops
            assert 'impacted_stops' not in dis['impacted_objects'][0]

        # We should see the disruption
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 1
        _check_train_cancel_disruption(pt_response['disruptions'][0])

        # and we should be able to query for the vj's disruption
        disrup_response = self.query_region('vehicle_journeys/vehicle_journey:vjA/disruptions')
        assert len(disrup_response['disruptions']) == 1
        _check_train_cancel_disruption(disrup_response['disruptions'][0])

        traffic_reports_response = self.query_region('traffic_reports?_current_datetime=20120614T0800')
        traffic_reports = get_not_null(traffic_reports_response, 'traffic_reports')
        assert len(traffic_reports) == 1
        vjs = get_not_null(traffic_reports[0], "vehicle_journeys")
        assert len(vjs) == 1
        assert vjs[0]['id'] == 'vehicle_journey:vjA'

        new_response = self.query_region(journey_basic_query + "&data_freshness=realtime")
        assert set(get_arrivals(new_response)) == set(['20120614T080436', '20120614T080223'])
        assert get_used_vj(new_response) == [['vehicle_journey:vjM'], []]

        isochrone_realtime = self.query_region(isochrone_basic_query + "&data_freshness=realtime")
        is_valid_graphical_isochrone(
            isochrone_realtime, self.tester, isochrone_basic_query + "&data_freshness=realtime"
        )
        geojson_realtime = isochrone_realtime['isochrones'][0]['geojson']
        multi_poly_realtime = asShape(geojson_realtime)
        isochrone_base_schedule = self.query_region(isochrone_basic_query + "&data_freshness=base_schedule")
        is_valid_graphical_isochrone(
            isochrone_base_schedule, self.tester, isochrone_basic_query + "&data_freshness=base_schedule"
        )
        geojson_base_schedule = isochrone_base_schedule['isochrones'][0]['geojson']
        multi_poly_base_schedule = asShape(geojson_base_schedule)
        assert not multi_poly.difference(multi_poly_realtime).is_empty
        assert multi_poly.equals(multi_poly_base_schedule)

        # We have one less departure (vjA because of disruption)
        # The disruption doesn't appear because the lines departing aren't impacted during the period
        departures = self.query_region("stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800")
        assert len(departures['disruptions']) == 0
        assert len(departures['departures']) == 2

        # We still have 2 passages in base schedule, but we have the new disruption
        departures = self.query_region(
            "stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800&data_freshness=base_schedule"
        )
        assert len(departures['disruptions']) == 2
        assert len(departures['departures']) == 3

        # it should not have changed anything for the theoric
        new_base = self.query_region(journey_basic_query + "&data_freshness=base_schedule")
        assert get_arrivals(new_base) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(new_base) == [['vehicle_journey:vjA'], []]
        # see http://jira.canaltp.fr/browse/NAVP-266,
        # _current_datetime is needed to make it work
        # assert len(new_base['disruptions']) == 1

        # remove links as the calling url is not the same
        for j in new_base['journeys']:
            j.pop('links', None)
        for j in response['journeys']:
            j.pop('links', None)
        assert new_base['journeys'] == response['journeys']


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnVJDelay(MockKirinDisruptionsFixture):
    def test_vj_delay(self):
        """
        send a mock kirin vj delay and test that the vj is not taken
        """
        response = self.query_region(journey_basic_query + "&data_freshness=realtime")

        # with no cancellation, we have 2 journeys, one direct and one with the vj:A:0
        assert get_arrivals(response) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(response) == [['vehicle_journey:vjA'], []]

        # we have 3 departures and 1 disruption (linked to the first passage)
        departures = self.query_region("stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800")
        assert len(departures['disruptions']) == 1
        assert len(departures['departures']) == 3
        assert departures['departures'][0]['stop_date_time']['departure_date_time'] == '20120614T080100'

        pt_response = self.query_region('vehicle_journeys')
        initial_nb_vehicle_journeys = len(pt_response['vehicle_journeys'])
        assert initial_nb_vehicle_journeys == 7

        # no disruption yet
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 0

        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                    message='cow on tracks',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    arrival_delay=3 * 60 + 58,
                    departure_delay=3 * 60 + 58,
                ),
            ],
            disruption_id='vjA_delayed',
        )

        # A new vj is created, which the vj with the impact of the disruption
        pt_response = self.query_region('vehicle_journeys')
        assert len(pt_response['vehicle_journeys']) == (initial_nb_vehicle_journeys + 1)

        vj_ids = [vj['id'] for vj in pt_response['vehicle_journeys']]
        assert 'vehicle_journey:vjA:modified:0:vjA_delayed' in vj_ids

        def _check_train_delay_disruption(dis):
            is_valid_disruption(dis, chaos_disrup=False)
            assert dis['disruption_id'] == 'vjA_delayed'
            assert dis['severity']['effect'] == 'SIGNIFICANT_DELAYS'
            assert len(dis['impacted_objects']) == 1
            ptobj = dis['impacted_objects'][0]['pt_object']
            assert ptobj['embedded_type'] == 'trip'
            assert ptobj['id'] == 'vjA'
            assert ptobj['name'] == 'vjA'
            # for delay we should have detail on the impacted stops
            impacted_objs = get_not_null(dis['impacted_objects'][0], 'impacted_stops')
            assert len(impacted_objs) == 2
            imp_obj1 = impacted_objs[0]
            assert get_valid_time(get_not_null(imp_obj1, 'amended_arrival_time')) == _dt(h=8, m=2, s=24)
            assert get_valid_time(get_not_null(imp_obj1, 'amended_departure_time')) == _dt(h=8, m=2, s=25)
            assert get_not_null(imp_obj1, 'cause') == 'cow on tracks'
            assert get_not_null(imp_obj1, 'departure_status') == 'delayed'
            assert get_not_null(imp_obj1, 'arrival_status') == 'delayed'
            assert get_not_null(imp_obj1, 'stop_time_effect') == 'delayed'
            assert get_valid_time(get_not_null(imp_obj1, 'base_arrival_time')) == _dt(8, 1, 0)
            assert get_valid_time(get_not_null(imp_obj1, 'base_departure_time')) == _dt(8, 1, 0)

            imp_obj2 = impacted_objs[1]
            assert get_valid_time(get_not_null(imp_obj2, 'amended_arrival_time')) == _dt(h=8, m=4, s=0)
            assert get_valid_time(get_not_null(imp_obj2, 'amended_departure_time')) == _dt(h=8, m=4, s=0)
            assert imp_obj2['cause'] == ''
            assert get_not_null(imp_obj1, 'stop_time_effect') == 'delayed'
            assert get_not_null(imp_obj1, 'departure_status') == 'delayed'
            assert get_not_null(imp_obj1, 'arrival_status') == 'delayed'
            assert get_valid_time(get_not_null(imp_obj2, 'base_departure_time')) == _dt(8, 1, 2)
            assert get_valid_time(get_not_null(imp_obj2, 'base_arrival_time')) == _dt(8, 1, 2)

        # we should see the disruption
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 1
        _check_train_delay_disruption(pt_response['disruptions'][0])

        # In order to not disturb the test, line M which was added afterwards for shared section tests, is forbidden here
        new_response = self.query_region(journey_basic_query + "&data_freshness=realtime&forbidden_uris[]=M&")
        assert get_arrivals(new_response) == ['20120614T080436', '20120614T080520']
        assert get_used_vj(new_response) == [[], ['vehicle_journey:vjA:modified:0:vjA_delayed']]

        pt_journey = new_response['journeys'][1]

        check_journey(
            pt_journey,
            Journey(
                sections=[
                    Section(
                        departure_date_time='20120614T080208',
                        arrival_date_time='20120614T080225',
                        base_departure_date_time=None,
                        base_arrival_date_time=None,
                        stop_date_times=[],
                    ),
                    Section(
                        departure_date_time='20120614T080225',
                        arrival_date_time='20120614T080400',
                        base_departure_date_time='20120614T080100',
                        base_arrival_date_time='20120614T080102',
                        stop_date_times=[
                            SectionStopDT(
                                departure_date_time='20120614T080225',
                                arrival_date_time='20120614T080224',
                                base_departure_date_time='20120614T080100',
                                base_arrival_date_time='20120614T080100',
                            ),
                            SectionStopDT(
                                departure_date_time='20120614T080400',
                                arrival_date_time='20120614T080400',
                                base_departure_date_time='20120614T080102',
                                base_arrival_date_time='20120614T080102',
                            ),
                        ],
                    ),
                    Section(
                        departure_date_time='20120614T080400',
                        arrival_date_time='20120614T080520',
                        base_departure_date_time=None,
                        base_arrival_date_time=None,
                        stop_date_times=[],
                    ),
                ]
            ),
        )

        # it should not have changed anything for the theoric
        new_base = self.query_region(journey_basic_query + "&data_freshness=base_schedule")
        assert get_arrivals(new_base) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(new_base), [['vehicle_journey:vjA'] == []]

        # we have one delayed departure
        departures = self.query_region("stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800")
        assert len(departures['disruptions']) == 2
        assert len(departures['departures']) == 3
        assert departures['departures'][1]['stop_date_time']['departure_date_time'] == '20120614T080225'

        # Same as realtime except the departure date time
        departures = self.query_region(
            "stop_points/stop_point:stopB/departures?_current_datetime=20120614T0800&data_freshness=base_schedule"
        )
        assert len(departures['disruptions']) == 2
        assert len(departures['departures']) == 3
        assert departures['departures'][0]['stop_date_time']['departure_date_time'] == '20120614T080100'

        # We send again the same disruption
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                    message='cow on tracks',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    arrival_delay=3 * 60 + 58,
                    departure_delay=3 * 60 + 58,
                ),
            ],
            disruption_id='vjA_delayed',
        )

        # A new vj is created, but a useless vj has been cleaned, so the number of vj does not change
        pt_response = self.query_region('vehicle_journeys')
        assert len(pt_response['vehicle_journeys']) == (initial_nb_vehicle_journeys + 1)

        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 1
        _check_train_delay_disruption(pt_response['disruptions'][0])

        # So the first real-time vj created for the first disruption should be deactivated
        # In order to not disturb the test, line M which was added afterwards for shared section tests, is forbidden here
        new_response = self.query_region(journey_basic_query + "&data_freshness=realtime&forbidden_uris[]=M&")
        assert get_arrivals(new_response) == ['20120614T080436', '20120614T080520']
        assert get_used_vj(new_response), [[] == ['vehicle_journey:vjA:modified:1:vjA_delayed']]

        # it should not have changed anything for the theoric
        new_base = self.query_region(journey_basic_query + "&data_freshness=base_schedule")
        assert get_arrivals(new_base) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(new_base), [['vehicle_journey:vjA'] == []]

        # we then try to send a delay on another train.
        # we should not have lost the first delay
        self.send_mock(
            "vjB",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    tstamp("20120614T180224"),
                    tstamp("20120614T180225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    tstamp("20120614T180400"),
                    tstamp("20120614T180400"),
                    message="bob's in the place",
                ),
            ],
        )

        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 1
        _check_train_delay_disruption(pt_response['disruptions'][0])

        # we should also have the disruption on vjB
        assert (
            len(
                self.query_region('vehicle_journeys/vehicle_journey:vjB?_current_datetime=20120614T1337')[
                    'disruptions'
                ]
            )
            == 1
        )

        ###################################
        # We now send a partial delete on B
        ###################################
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB", arrival=tstamp("20120614T080100"), departure=tstamp("20120614T080100")
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                    message='cow on tracks',
                    arrival_skipped=True,
                ),
            ],
            disruption_id='vjA_skip_A',
        )

        # A new vj is created
        vjs = self.query_region('vehicle_journeys?_current_datetime=20120614T1337')
        assert len(vjs['vehicle_journeys']) == (initial_nb_vehicle_journeys + 2)

        vjA = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        # we now have 2 disruption on vjA
        assert len(vjA['disruptions']) == 2
        all_dis = {d['id']: d for d in vjA['disruptions']}
        assert 'vjA_skip_A' in all_dis

        dis = all_dis['vjA_skip_A']

        is_valid_disruption(dis, chaos_disrup=False)
        assert dis['disruption_id'] == 'vjA_skip_A'
        assert dis['severity']['effect'] == 'REDUCED_SERVICE'
        assert len(dis['impacted_objects']) == 1
        ptobj = dis['impacted_objects'][0]['pt_object']
        assert ptobj['embedded_type'] == 'trip'
        assert ptobj['id'] == 'vjA'
        assert ptobj['name'] == 'vjA'
        # for delay we should have detail on the impacted stops
        impacted_objs = get_not_null(dis['impacted_objects'][0], 'impacted_stops')
        assert len(impacted_objs) == 2
        imp_obj1 = impacted_objs[0]
        assert get_valid_time(get_not_null(imp_obj1, 'amended_arrival_time')) == _dt(8, 1, 0)
        assert get_valid_time(get_not_null(imp_obj1, 'amended_departure_time')) == _dt(8, 1, 0)
        assert get_not_null(imp_obj1, 'stop_time_effect') == 'unchanged'
        assert get_not_null(imp_obj1, 'arrival_status') == 'unchanged'
        assert get_not_null(imp_obj1, 'departure_status') == 'unchanged'
        assert get_valid_time(get_not_null(imp_obj1, 'base_arrival_time')) == _dt(8, 1, 0)
        assert get_valid_time(get_not_null(imp_obj1, 'base_departure_time')) == _dt(8, 1, 0)

        imp_obj2 = impacted_objs[1]
        assert 'amended_arrival_time' not in imp_obj2
        assert get_not_null(imp_obj2, 'cause') == 'cow on tracks'
        assert get_not_null(imp_obj2, 'stop_time_effect') == 'deleted'  # the stoptime is marked as deleted
        assert get_not_null(imp_obj2, 'arrival_status') == 'deleted'
        assert get_not_null(imp_obj2, 'departure_status') == 'unchanged'  # the departure is not changed
        assert get_valid_time(get_not_null(imp_obj2, 'base_departure_time')) == _dt(8, 1, 2)
        assert get_valid_time(get_not_null(imp_obj2, 'base_arrival_time')) == _dt(8, 1, 2)


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnVJDelayDayAfter(MockKirinDisruptionsFixture):
    def test_vj_delay_day_after(self):
        """
        send a mock kirin vj delaying on day after and test that the vj is not taken
        """
        response = self.query_region(journey_basic_query + "&data_freshness=realtime")
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')

        # with no cancellation, we have 2 journeys, one direct and one with the vj:A:0
        assert get_arrivals(response) == ['20120614T080222', '20120614T080436']  # pt_walk + vj 08:01
        assert get_used_vj(response), [['vjA'] == []]

        pt_response = self.query_region('vehicle_journeys')
        initial_nb_vehicle_journeys = len(pt_response['vehicle_journeys'])
        assert initial_nb_vehicle_journeys == 7

        # check that we have the next vj
        s_coord = "0.0000898312;0.0000898312"  # coordinate of S in the dataset
        r_coord = "0.00188646;0.00071865"  # coordinate of R in the dataset
        journey_later_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord=s_coord, to_coord=r_coord, datetime="20120614T080500"
        )
        later_response = self.query_region(journey_later_query + "&data_freshness=realtime")
        assert get_arrivals(later_response) == ['20120614T080936', '20120614T180222']  # pt_walk + vj 18:01
        assert get_used_vj(later_response), [[] == ['vehicle_journey:vjB']]

        # no disruption yet
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 0

        # sending disruption delaying VJ to the next day
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime("stop_point:stopB", tstamp("20120615T070224"), tstamp("20120615T070224")),
                UpdatedStopTime("stop_point:stopA", tstamp("20120615T070400"), tstamp("20120615T070400")),
            ],
            disruption_id='96231_2015-07-28_0',
            effect='unknown',
        )

        # A new vj is created
        pt_response = self.query_region('vehicle_journeys')
        assert len(pt_response['vehicle_journeys']) == (initial_nb_vehicle_journeys + 1)

        vj_ids = [vj['id'] for vj in pt_response['vehicle_journeys']]
        assert 'vehicle_journey:vjA:modified:0:96231_2015-07-28_0' in vj_ids

        # we should see the disruption
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')
        assert len(pt_response['disruptions']) == 1
        is_valid_disruption(pt_response['disruptions'][0], chaos_disrup=False)
        assert pt_response['disruptions'][0]['disruption_id'] == '96231_2015-07-28_0'

        # In order to not disturb the test, line M which was added afterwards for shared section tests, is forbidden here
        new_response = self.query_region(journey_basic_query + "&data_freshness=realtime&forbidden_uris[]=M&")
        assert get_arrivals(new_response) == ['20120614T080436', '20120614T180222']  # pt_walk + vj 18:01
        assert get_used_vj(new_response), [[] == ['vjB']]

        # it should not have changed anything for the theoric
        new_base = self.query_region(journey_basic_query + "&data_freshness=base_schedule")
        assert get_arrivals(new_base) == ['20120614T080222', '20120614T080436']
        assert get_used_vj(new_base), [['vjA'] == []]

        # the day after, we can use the delayed vj
        journey_day_after_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord=s_coord, to_coord=r_coord, datetime="20120615T070000"
        )
        day_after_response = self.query_region(journey_day_after_query + "&data_freshness=realtime")
        assert get_arrivals(day_after_response) == [
            '20120615T070436',
            '20120615T070520',
        ]  # pt_walk + rt 07:02:24
        assert get_used_vj(day_after_response), [[] == ['vehicle_journey:vjA:modified:0:96231_2015-07-28_0']]

        # it should not have changed anything for the theoric the day after
        day_after_base = self.query_region(journey_day_after_query + "&data_freshness=base_schedule")
        assert get_arrivals(day_after_base) == ['20120615T070436', '20120615T080222']
        assert get_used_vj(day_after_base), [[] == ['vjA']]


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnVJOnTime(MockKirinDisruptionsFixture):
    def test_vj_on_time(self):
        """
        We don't want to output an on time disruption on journeys,
        departures, arrivals and route_schedules (also on
        stop_schedules, but no vj disruption is outputed for the
        moment).
        """
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption same as base schedule
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='vjA_on_time',
            effect='unknown',
        )

        # We have a new diruption
        disruptions_after = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])
        assert has_the_disruption(disruptions_after, 'vjA_on_time')

        # it's not in journeys
        journey_query = journey_basic_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(journey_query)
        assert not has_the_disruption(response, 'vjA_on_time')
        self.is_valid_journey_response(response, journey_query)
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'

        # it's not in departures
        response = self.query_region(
            "stop_points/stop_point:stopB/departures?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert not has_the_disruption(response, 'vjA_on_time')
        assert response['departures'][0]['stop_date_time']['data_freshness'] == 'realtime'

        # it's not in arrivals
        response = self.query_region(
            "stop_points/stop_point:stopA/arrivals?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert not has_the_disruption(response, 'vjA_on_time')
        assert response['arrivals'][0]['stop_date_time']['data_freshness'] == 'realtime'

        # it's not in stop_schedules
        response = self.query_region(
            "stop_points/stop_point:stopB/lines/A/stop_schedules?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert not has_the_disruption(response, 'vjA_on_time')
        assert response['stop_schedules'][0]['date_times'][0]['data_freshness'] == 'realtime'
        assert response['stop_schedules'][0]['date_times'][0]['base_date_time'] == '20120614T080100'
        assert response['stop_schedules'][0]['date_times'][0]['date_time'] == '20120614T080100'

        # it's not in route_schedules
        response = self.query_region(
            "stop_points/stop_point:stopB/lines/A/route_schedules?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert not has_the_disruption(response, 'vjA_on_time')
        # no realtime flags on route_schedules yet

        # New disruption one second late
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=1,
                    departure_delay=1,
                    arrival=tstamp("20120614T080101"),
                    departure=tstamp("20120614T080101"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=1,
                    departure_delay=1,
                    arrival=tstamp("20120614T080103"),
                    departure=tstamp("20120614T080103"),
                ),
            ],
            disruption_id='vjA_late',
        )

        # We have a new diruption
        disruptions_after = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert nb_disruptions_before + 2 == len(disruptions_after['disruptions'])
        assert has_the_disruption(disruptions_after, 'vjA_late')

        # it's in journeys
        response = self.query_region(journey_query)
        assert has_the_disruption(response, 'vjA_late')
        self.is_valid_journey_response(response, journey_query)
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'

        # it's in departures
        response = self.query_region(
            "stop_points/stop_point:stopB/departures?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert has_the_disruption(response, 'vjA_late')
        assert response['departures'][0]['stop_date_time']['departure_date_time'] == '20120614T080101'
        assert response['departures'][0]['stop_date_time']['data_freshness'] == 'realtime'

        # it's in arrivals
        response = self.query_region(
            "stop_points/stop_point:stopA/arrivals?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert has_the_disruption(response, 'vjA_late')
        assert response['arrivals'][0]['stop_date_time']['arrival_date_time'] == '20120614T080103'
        assert response['arrivals'][0]['stop_date_time']['data_freshness'] == 'realtime'

        # it's in stop_schedules
        response = self.query_region(
            "stop_points/stop_point:stopB/lines/A/stop_schedules?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert has_the_disruption(response, 'vjA_late')
        assert response['stop_schedules'][0]['date_times'][0]['links'][1]['type'] == 'disruption'
        assert response['stop_schedules'][0]['date_times'][0]['date_time'] == '20120614T080101'
        assert response['stop_schedules'][0]['date_times'][0]['base_date_time'] == '20120614T080100'
        assert response['stop_schedules'][0]['date_times'][0]['data_freshness'] == 'realtime'

        # it's in route_schedules
        response = self.query_region(
            "stop_points/stop_point:stopB/lines/A/route_schedules?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        assert has_the_disruption(response, 'vjA_late')
        # no realtime flags on route_schedules yet


MAIN_ROUTING_TEST_SETTING_NO_ADD = {
    'main_routing_test': {
        'kraken_args': [
            '--BROKER.rt_topics=' + rt_topic,
            'spawn_maintenance_worker',
        ]  # also check that by 'default is_realtime_add_enabled=0'
    }
}


MAIN_ROUTING_TEST_SETTING = deepcopy(MAIN_ROUTING_TEST_SETTING_NO_ADD)
MAIN_ROUTING_TEST_SETTING['main_routing_test']['kraken_args'].append('--GENERAL.is_realtime_add_enabled=1')
MAIN_ROUTING_TEST_SETTING['main_routing_test']['kraken_args'].append('--GENERAL.is_realtime_add_trip_enabled=1')


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnNewStopTimeAtTheEnd(MockKirinDisruptionsFixture):
    def test_add_and_delete_one_stop_time_at_the_end(self):
        """
        1. create a new_stop_time to add a final stop in C
        test that a new journey is possible with section type = public_transport from B to C
        2. delete the added stop_time and verify that the public_transport section is absent
        3. delete again stop_time and verify that the public_transport section is absent
        """
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption with two stop_times same as base schedule and
        # a new stop_time on stop_point:stopC added at the end
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                ),
            ],
            disruption_id='new_stop_time',
        )

        # We have a new disruption to add a new stop_time at stop_point:stopC in vehicle_journey 'VJA'
        disruptions_after = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])
        assert has_the_disruption(disruptions_after, 'new_stop_time')
        last_disrupt = disruptions_after['disruptions'][-1]
        assert last_disrupt['severity']['effect'] == 'MODIFIED_SERVICE'

        journey_query = journey_basic_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(journey_query)
        assert has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, journey_query)
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][1]['display_informations']['physical_mode'] == 'Tramway'

        B_C_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord='stop_point:stopB', to_coord='stop_point:stopC', datetime='20120614T080000'
        )

        # The result with base_schedule should not have a journey with public_transport from B to C
        base_journey_query = B_C_query + "&data_freshness=base_schedule&_current_datetime=20120614T080000"
        response = self.query_region(base_journey_query)
        assert not has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, base_journey_query)
        assert len(response['journeys']) == 1  # check we only have one journey
        assert len(response['journeys'][0]['sections']) == 1
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]  # means it's base_schedule

        # The result with realtime should have a journey with public_transport from B to C
        rt_journey_query = B_C_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(rt_journey_query)
        assert has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, rt_journey_query)
        assert len(response['journeys']) == 2  # check there's a new journey possible
        assert response['journeys'][0]['sections'][0]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][0]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][0]['to']['id'] == 'stop_point:stopC'
        assert response['journeys'][0]['sections'][0]['duration'] == 4
        assert response['journeys'][0]['status'] == 'MODIFIED_SERVICE'
        assert 'data_freshness' not in response['journeys'][1]['sections'][0]  # means it's base_schedule
        assert response['journeys'][1]['sections'][0]['type'] == 'street_network'

        # New disruption with a deleted stop_time recently added at stop_point:stopC
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                    message='stop_time deleted',
                    arrival_skipped=True,
                )
            ],
            disruption_id='deleted_stop_time',
        )

        # We have a new disruption with a deleted stop_time at stop_point:stopC in vehicle_journey 'VJA'
        disruptions_with_deleted = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disruptions_after['disruptions']) + 1 == len(disruptions_with_deleted['disruptions'])
        assert has_the_disruption(disruptions_with_deleted, 'deleted_stop_time')

        # The result with realtime should not have a journey with public_transport from B to C
        # since the added stop_time has been deleted by the last disruption
        rt_journey_query = B_C_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(rt_journey_query)
        assert not has_the_disruption(response, 'added_stop_time')
        self.is_valid_journey_response(response, rt_journey_query)
        assert len(response['journeys']) == 1
        assert len(response['journeys'][0]['sections']) == 1
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]

        # New disruption with a deleted stop_time already deleted at stop_point:stopC
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                    message='stop_time deleted',
                    arrival_skipped=True,
                )
            ],
            disruption_id='re_deleted_stop_time',
        )

        # We have a new disruption with a deleted stop_time at stop_point:stopC in vehicle_journey 'VJA'
        disruptions_with_deleted = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disruptions_after['disruptions']) + 2 == len(disruptions_with_deleted['disruptions'])
        assert has_the_disruption(disruptions_with_deleted, 're_deleted_stop_time')

        # The result with realtime should not have a journey with public_transport from B to C
        rt_journey_query = B_C_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(rt_journey_query)
        assert not has_the_disruption(response, 'added_stop_time')
        self.is_valid_journey_response(response, rt_journey_query)
        assert len(response['journeys']) == 1


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinReadTripEffectFromTripUpdate(MockKirinDisruptionsFixture):
    def test_read_trip_effect_from_tripupdate(self):
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])
        assert nb_disruptions_before == 11

        vjs_before = self.query_region('vehicle_journeys')
        assert len(vjs_before['vehicle_journeys']) == 7

        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=0,
                    departure_delay=0,
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    message='stop_time deleted',
                    arrival_skipped=True,
                    departure_skipped=True,
                ),
            ],
            disruption_id='reduced_service_vjA',
            effect='reduced_service',
        )
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 12
        assert has_the_disruption(disrupts, 'reduced_service_vjA')
        last_disrupt = disrupts['disruptions'][-1]
        assert last_disrupt['severity']['effect'] == 'REDUCED_SERVICE'
        assert last_disrupt['severity']['name'] == 'reduced service'

        vjs_after = self.query_region('vehicle_journeys')
        # we got a new vj due to the disruption, which means the disruption is handled correctly
        assert len(vjs_after['vehicle_journeys']) == 8


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnNewStopTimeInBetween(MockKirinDisruptionsFixture):
    def test_add_modify_and_delete_one_stop_time(self):
        """
        1. Create a disruption with delay on VJ = vjA (with stop_time B and A) and verify the journey
        for a query from S to R: S-> walk-> B -> public_transport -> A -> walk -> R
        2. Add a new stop_time (stop_point C) in between B and A in the VJ = vjA and verify the journey as above
        3. Verify the journey for a query from S to C: S-> walk-> B -> public_transport -> C
        4. Delete the added stop_time and verify the journey  for a query in 3.
        """
        # New disruption with a delay of VJ = vjA
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                    message='cow on tracks',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    arrival_delay=3 * 60 + 58,
                    departure_delay=3 * 60 + 58,
                ),
            ],
            disruption_id='vjA_delayed',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 12
        assert has_the_disruption(disrupts, 'vjA_delayed')

        # query from S to R: Journey without delay with departure from B at 20120614T080100
        # and arrival to A  at 20120614T080102 returned
        response = self.query_region(journey_basic_query + "&data_freshness=realtime")
        assert len(response['journeys']) == 2
        assert len(response['journeys'][0]['sections']) == 3
        assert len(response['journeys'][1]['sections']) == 1
        assert response['journeys'][0]['sections'][1]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'base_schedule'
        assert response['journeys'][0]['sections'][1]['departure_date_time'] == '20120614T080101'
        assert response['journeys'][0]['sections'][1]['arrival_date_time'] == '20120614T080103'
        assert len(response['journeys'][0]['sections'][1]['stop_date_times']) == 2
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'

        # A new request with departure after 2 minutes gives us journey with delay
        response = self.query_region(sub_query + "&data_freshness=realtime&datetime=20120614T080200")
        assert len(response['journeys']) == 2
        assert len(response['journeys'][0]['sections']) == 3
        assert len(response['journeys'][1]['sections']) == 1
        assert response['journeys'][0]['sections'][1]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][1]['departure_date_time'] == '20120614T080225'
        assert response['journeys'][0]['sections'][1]['arrival_date_time'] == '20120614T080400'
        assert len(response['journeys'][0]['sections'][1]['stop_date_times']) == 2
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'

        # New disruption with a new stop_time in between B and A of the VJ = vjA
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                    message='cow on tracks',
                ),
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080330"),
                    departure=tstamp("20120614T080330"),
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    arrival_delay=3 * 60 + 58,
                    departure_delay=3 * 60 + 58,
                ),
            ],
            disruption_id='vjA_delayed_with_new_stop_time',
            effect='detour',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 13
        assert has_the_disruption(disrupts, 'vjA_delayed_with_new_stop_time')
        last_disrupt = disrupts['disruptions'][-1]
        assert last_disrupt['severity']['effect'] == 'DETOUR'

        # the journey has the new stop_time in its section of public_transport
        response = self.query_region(sub_query + "&data_freshness=realtime&datetime=20120614T080200")
        assert len(response['journeys']) == 2
        assert len(response['journeys'][0]['sections']) == 3
        assert len(response['journeys'][1]['sections']) == 1
        assert response['journeys'][0]['sections'][1]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][1]['departure_date_time'] == '20120614T080225'
        assert response['journeys'][0]['sections'][1]['arrival_date_time'] == '20120614T080400'
        assert len(response['journeys'][0]['sections'][1]['stop_date_times']) == 3
        assert (
            response['journeys'][0]['sections'][1]['stop_date_times'][1]['stop_point']['name']
            == 'stop_point:stopC'
        )
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'

        # Query from S to C: Uses a public_transport from B to C
        S_to_C_query = "journeys?from={from_coord}&to={to_coord}".format(
            from_coord='0.0000898312;0.0000898312', to_coord='stop_point:stopC'
        )
        base_journey_query = S_to_C_query + "&data_freshness=realtime&datetime=20120614T080200"
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 2
        assert len(response['journeys'][0]['sections']) == 2
        assert len(response['journeys'][1]['sections']) == 1
        assert response['journeys'][0]['sections'][1]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][1]['departure_date_time'] == '20120614T080225'
        assert response['journeys'][0]['sections'][1]['arrival_date_time'] == '20120614T080330'

        # New disruption with a deleted stop_time recently added at stop_point:stopC
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080330"),
                    departure=tstamp("20120614T080330"),
                    message='stop_time deleted',
                    arrival_skipped=True,
                )
            ],
            disruption_id='deleted_stop_time',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 14
        assert has_the_disruption(disrupts, 'deleted_stop_time')

        # the journey doesn't have public_transport
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 1
        assert len(response['journeys'][0]['sections']) == 1
        assert response['journeys'][0]['type'] == 'best'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinOnNewStopTimeAtTheBeginning(MockKirinDisruptionsFixture):
    def test_add_modify_and_delete_one_stop_time(self):
        """
        1. create a new_stop_time to add a final stop in C
        test that a new journey is possible with section type = public_transport from B to C
        2. delete the added stop_time and verify that the public_transport section is absent
        3. delete again stop_time and verify that the public_transport section is absent
        """
        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 11

        C_to_R_query = "journeys?from={from_coord}&to={to_coord}".format(
            from_coord='stop_point:stopC', to_coord='0.00188646;0.00071865'
        )

        # Query from C to R: the journey doesn't have any public_transport
        base_journey_query = C_to_R_query + "&data_freshness=realtime&datetime=20120614T080000"
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 1
        assert len(response['journeys'][0]['sections']) == 1
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]
        assert response['journeys'][0]['durations']['walking'] == 159

        # New disruption with two stop_times same as base schedule and
        # a new stop_time on stop_point:stopC added at the beginning
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080055"),
                    departure=tstamp("20120614T080055"),
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_stop_time',
            effect='delayed',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 12
        assert has_the_disruption(disrupts, 'new_stop_time')
        last_disruption = disrupts['disruptions'][-1]
        assert last_disruption['impacted_objects'][0]['impacted_stops'][0]['arrival_status'] == 'added'
        assert last_disruption['impacted_objects'][0]['impacted_stops'][0]['departure_status'] == 'added'
        assert last_disruption['severity']['effect'] == 'SIGNIFICANT_DELAYS'
        assert last_disruption['severity']['name'] == 'trip delayed'

        # Query from C to R: the journey should have a public_transport from C to A
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 2
        assert len(response['journeys'][0]['sections']) == 2
        assert response['journeys'][0]['sections'][0]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][0]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][0]['departure_date_time'] == '20120614T080055'
        assert response['journeys'][0]['sections'][1]['arrival_date_time'] == '20120614T080222'
        assert response['journeys'][1]['sections'][0]['type'] == 'street_network'

        # New disruption with a deleted stop_time recently added at stop_point:stopC
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                    message='stop_time deleted',
                    arrival_skipped=True,
                )
            ],
            disruption_id='deleted_stop_time',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == 13
        assert has_the_disruption(disrupts, 'deleted_stop_time')
        last_disruption = disrupts['disruptions'][-1]
        assert last_disruption['impacted_objects'][0]['impacted_stops'][0]['arrival_status'] == 'deleted'
        assert (
            last_disruption['impacted_objects'][0]['impacted_stops'][0]['departure_status'] == 'unchanged'
        )  # Why?
        assert last_disruption['severity']['effect'] == 'REDUCED_SERVICE'
        assert last_disruption['severity']['name'] == 'reduced service'

        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 1
        assert len(response['journeys'][0]['sections']) == 1
        assert response['journeys'][0]['sections'][0]['type'] == 'street_network'
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]
        assert response['journeys'][0]['durations']['walking'] == 159

        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T080000')
        assert len(pt_response['disruptions']) == 2


@dataset(MAIN_ROUTING_TEST_SETTING_NO_ADD)
class TestKrakenNoAdd(MockKirinDisruptionsFixture):
    def test_no_rt_add_possible(self):
        """
        trying to add new_stop_time without allowing it in kraken
        test that it is ignored
        (same test as test_add_one_stop_time_at_the_end(), different result expected)
        """
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption same as base schedule
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                ),
            ],
            disruption_id='new_stop_time',
        )

        # No new disruption
        disruptions_after = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert nb_disruptions_before == len(disruptions_after['disruptions'])
        assert not has_the_disruption(disruptions_after, 'new_stop_time')

        journey_query = journey_basic_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(journey_query)
        assert not has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, journey_query)
        assert response['journeys'][0]['sections'][1]['data_freshness'] == 'base_schedule'

        B_C_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord='stop_point:stopB', to_coord='stop_point:stopC', datetime='20120614T080000'
        )
        base_journey_query = B_C_query + "&data_freshness=base_schedule&_current_datetime=20120614T080000"
        response = self.query_region(base_journey_query)
        assert not has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, base_journey_query)
        assert len(response['journeys']) == 1  # check we only have one journey
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]  # means it's base_schedule

        B_C_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord='stop_point:stopB', to_coord='stop_point:stopC', datetime='20120614T080000'
        )
        rt_journey_query = B_C_query + "&data_freshness=realtime&_current_datetime=20120614T080000"
        response = self.query_region(rt_journey_query)
        assert not has_the_disruption(response, 'new_stop_time')
        self.is_valid_journey_response(response, rt_journey_query)
        assert len(response['journeys']) == 1  # check there's no new journey possible
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]  # means it's base_schedule


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinStopTimeOnDetourAtTheEnd(MockKirinDisruptionsFixture):
    def test_stop_time_with_detour_at_the_end(self):
        """
        1. create a new_stop_time at C to replace existing one at A so that we have
            A deleted_for_detour and C added_for_detour
        2. test that a new journey is possible with section type = public_transport from B to C
        """
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption with one stop_time same as base schedule, another one deleted and
        # a new stop_time on stop_point:stopC added at the end
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                    arrival_skipped=True,
                    is_detour=True,
                    message='deleted for detour',
                ),
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080104"),
                    departure=tstamp("20120614T080104"),
                    is_added=True,
                    is_detour=True,
                    message='added for detour',
                ),
            ],
            disruption_id='stop_time_with_detour',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == nb_disruptions_before + 1
        assert has_the_disruption(disrupts, 'stop_time_with_detour')
        last_disrupt = disrupts['disruptions'][-1]
        assert last_disrupt['severity']['effect'] == 'DETOUR'

        # Verify impacted objects
        assert len(last_disrupt['impacted_objects']) == 1
        impacted_stops = last_disrupt['impacted_objects'][0]['impacted_stops']
        assert len(impacted_stops) == 3
        assert bool(impacted_stops[0]['is_detour']) is False
        assert impacted_stops[0]['cause'] == 'on time'

        assert bool(impacted_stops[1]['is_detour']) is True
        assert impacted_stops[1]['cause'] == 'deleted for detour'
        assert impacted_stops[1]['departure_status'] == 'unchanged'
        assert impacted_stops[1]['arrival_status'] == 'deleted'

        assert bool(impacted_stops[2]['is_detour']) is True
        assert impacted_stops[2]['cause'] == 'added for detour'
        assert impacted_stops[2]['departure_status'] == 'added'
        assert impacted_stops[2]['arrival_status'] == 'added'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinStopTimeOnDetourAndArrivesBeforeDeletedAtTheEnd(MockKirinDisruptionsFixture):
    def test_stop_time_with_detour_and_arrival_before_deleted_at_the_end(self):
        """
        1. create a new_stop_time at C to replace existing one at A so that we have A deleted_for_detour
        and C added_for_detour with arrival time < to arrival time of A (deleted)
        2. Kraken accepts this disruption
        """
        disruptions_before = self.query_region('disruptions?_current_datetime=20120614T080000')
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption with one stop_time same as base schedule, another one deleted and
        # a new stop_time on stop_point:stopC added at the end
        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                    arrival_skipped=True,
                    departure_skipped=True,
                    is_detour=True,
                    message='deleted for detour',
                ),
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    arrival=tstamp("20120614T080101"),
                    departure=tstamp("20120614T080101"),
                    is_added=True,
                    is_detour=True,
                    message='added for detour',
                ),
            ],
            disruption_id='stop_time_with_detour',
        )

        # Verify disruptions
        disrupts = self.query_region('disruptions?_current_datetime=20120614T080000')
        assert len(disrupts['disruptions']) == nb_disruptions_before + 1
        assert has_the_disruption(disrupts, 'stop_time_with_detour')
        last_disrupt = disrupts['disruptions'][-1]
        assert last_disrupt['severity']['effect'] == 'DETOUR'

        # Verify impacted objects
        assert len(last_disrupt['impacted_objects']) == 1
        impacted_stops = last_disrupt['impacted_objects'][0]['impacted_stops']
        assert len(impacted_stops) == 3
        assert bool(impacted_stops[0]['is_detour']) is False
        assert impacted_stops[0]['cause'] == 'on time'

        assert bool(impacted_stops[1]['is_detour']) is True
        assert impacted_stops[1]['cause'] == 'deleted for detour'
        assert impacted_stops[1]['departure_status'] == 'deleted'
        assert impacted_stops[1]['arrival_status'] == 'deleted'

        assert bool(impacted_stops[2]['is_detour']) is True
        assert impacted_stops[2]['cause'] == 'added for detour'
        assert impacted_stops[2]['departure_status'] == 'added'
        assert impacted_stops[2]['arrival_status'] == 'added'

        B_C_query = "journeys?from={from_coord}&to={to_coord}&datetime={datetime}".format(
            from_coord='stop_point:stopB', to_coord='stop_point:stopC', datetime='20120614T080000'
        )

        # Query with data_freshness=base_schedule
        base_journey_query = B_C_query + "&data_freshness=base_schedule&_current_datetime=20120614T080000"

        # There is no public transport from B to C
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 1
        assert response['journeys'][0]['type'] == 'best'
        assert 'data_freshness' not in response['journeys'][0]['sections'][0]  # means it's base_schedule

        # Query with data_freshness=realtime
        base_journey_query = B_C_query + "&data_freshness=realtime&_current_datetime=20120614T080000"

        # There is a public transport from B to C with realtime
        response = self.query_region(base_journey_query)
        assert len(response['journeys']) == 2
        assert response['journeys'][0]['status'] == 'DETOUR'
        assert response['journeys'][0]['sections'][0]['type'] == 'public_transport'
        assert response['journeys'][0]['sections'][0]['data_freshness'] == 'realtime'
        assert response['journeys'][0]['sections'][0]['display_informations']['physical_mode'] == 'Tramway'
        assert has_the_disruption(response, 'stop_time_with_detour')

        # Tramway is the first physical_mode in NTFS, but we might pick mode in a smarter way in the future
        response = self.query_region('physical_modes')
        assert response['physical_modes'][0]['name'] == 'Tramway'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddNewTrip(MockKirinDisruptionsFixture):
    def test_add_new_trip(self):
        """
        0. test that no PT-Ref object related to the new trip exists and that no PT-journey exists
        1. create a new trip
        2. test that journey is possible using this new trip
        3. test some PT-Ref objects were created
        4. test that /pt_objects returns those objects
        5. test that PT-Ref filters are working
        6. test /departures and stop_schedules
        """
        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # /journeys before (only direct walk)
        C_B_query = (
            "journeys?from={f}&to={to}&data_freshness=realtime&"
            "datetime={dt}&_current_datetime={dt}".format(
                f='stop_point:stopC', to='stop_point:stopB', dt='20120614T080000'
            )
        )
        response = self.query_region(C_B_query)
        assert not has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 1
        assert 'non_pt_walking' in response['journeys'][0]['tags']

        # /pt_objects before
        ptobj_query = 'pt_objects?q={q}&_current_datetime={dt}'.format(q='adi', dt='20120614T080000')  # ++typo
        response = self.query_region(ptobj_query)
        assert 'pt_objects' not in response

        # Check that no vehicle_journey exists on the future realtime-trip
        vj_query = 'vehicle_journeys/{vj}?_current_datetime={dt}'.format(
            vj='vehicle_journey:additional-trip:modified:0:new_trip', dt='20120614T080000'
        )
        response, status = self.query_region(vj_query, check=False)
        assert status == 404
        assert 'vehicle_journeys' not in response

        # Check that no additional line exists
        line_query = 'lines/{l}?_current_datetime={dt}'.format(l='line:stopC_stopB', dt='20120614T080000')
        response, status = self.query_region(line_query, check=False)
        assert status == 404
        assert 'lines' not in response

        # Check that PT-Ref filter fails as no object exists
        vj_filter_query = 'commercial_modes/{cm}/vehicle_journeys?_current_datetime={dt}'.format(
            cm='commercial_mode:additional_service', dt='20120614T080000'
        )
        response, status = self.query_region(vj_filter_query, check=False)
        assert status == 404
        assert response['error']['message'] == 'ptref : Filters: Unable to find object'

        network_filter_query = 'vehicle_journeys/{vj}/networks?_current_datetime={dt}'.format(
            vj='vehicle_journey:additional-trip:modified:0:new_trip', dt='20120614T080000'
        )
        response, status = self.query_region(network_filter_query, check=False)
        assert status == 404
        assert response['error']['message'] == 'ptref : Filters: Unable to find object'

        # Check that no departure exist on stop_point stop_point:stopC for neither base_schedule nor realtime
        departure_query = "stop_points/stop_point:stopC/departures?_current_datetime=20120614T080000"
        departures = self.query_region(departure_query + '&data_freshness=base_schedule')
        assert len(departures['departures']) == 0
        departures = self.query_region(departure_query + '&data_freshness=realtime')
        assert len(departures['departures']) == 0

        # Check stop_schedules on stop_point stop_point:stopC for base_schedule and realtime with
        # Date_times list empty
        ss_on_sp_query = "stop_points/stop_point:stopC/stop_schedules?_current_datetime=20120614T080000"
        stop_schedules = self.query_region(ss_on_sp_query + '&data_freshness=realtime')
        assert len(stop_schedules['stop_schedules']) == 1
        assert stop_schedules['stop_schedules'][0]['links'][0]['type'] == 'line'
        assert stop_schedules['stop_schedules'][0]['links'][0]['id'] == 'D'
        assert len(stop_schedules['stop_schedules'][0]['date_times']) == 0

        # Check that no stop_schedule exist on line:stopC_stopB and stop_point stop_point:stopC
        ss_on_line_query = (
            "stop_points/stop_point:stopC/lines/line:stopC_stopB/"
            "stop_schedules?_current_datetime=20120614T080000"
        )
        stop_schedules, status = self.query_region(ss_on_line_query + '&data_freshness=realtime', check=False)
        assert status == 404
        assert len(stop_schedules['stop_schedules']) == 0

        # New disruption, a new trip with 2 stop_times in realtime
        self.send_mock(
            "additional-trip",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
            physical_mode_id='physical_mode:Bus',  # this physical mode exists in kraken
        )

        # Check new disruption 'additional-trip' to add a new trip
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])
        new_trip_disruptions = get_disruptions_by_id(disruptions_after, 'new_trip')
        assert len(new_trip_disruptions) == 1
        new_trip_disrupt = new_trip_disruptions[0]
        assert new_trip_disrupt['id'] == 'new_trip'
        assert new_trip_disrupt['severity']['effect'] == 'ADDITIONAL_SERVICE'
        assert len(new_trip_disrupt['impacted_objects'][0]['impacted_stops']) == 2
        assert all(
            [
                (s['departure_status'] == 'added' and s['arrival_status'] == 'added')
                for s in new_trip_disrupt['impacted_objects'][0]['impacted_stops']
            ]
        )
        assert new_trip_disrupt['application_periods'][0]['begin'] == '20120614T080100'
        assert new_trip_disrupt['application_periods'][0]['end'] == '20120614T080101'  # last second is excluded

        # Check that a PT journey now exists
        response = self.query_region(C_B_query)
        assert has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 2
        pt_journey = response['journeys'][0]
        assert 'non_pt_walking' not in pt_journey['tags']
        assert pt_journey['status'] == 'ADDITIONAL_SERVICE'
        assert pt_journey['sections'][0]['data_freshness'] == 'realtime'
        assert pt_journey['sections'][0]['display_informations']['commercial_mode'] == 'additional service'
        assert pt_journey['sections'][0]['display_informations']['physical_mode'] == 'Bus'

        # Check /pt_objects after: new objects created
        response = self.query_region(ptobj_query)
        assert len(response['pt_objects']) == 4
        assert len([o for o in response['pt_objects'] if o['id'] == 'network:additional_service']) == 1
        assert len([o for o in response['pt_objects'] if o['id'] == 'commercial_mode:additional_service']) == 1
        assert len([o for o in response['pt_objects'] if o['id'] == 'line:stopC_stopB']) == 1
        assert len([o for o in response['pt_objects'] if o['id'] == 'route:stopC_stopB']) == 1

        # Check that the vehicle_journey has been created
        response = self.query_region(vj_query)
        assert has_the_disruption(response, 'new_trip')
        assert len(response['vehicle_journeys']) == 1
        assert response['vehicle_journeys'][0]['disruptions'][0]['id'] == 'new_trip'
        assert len(response['vehicle_journeys'][0]['stop_times']) == 2

        # Check that the new line has been created with necessary information
        response = self.query_region(line_query)
        assert len(response['lines']) == 1
        assert response['lines'][0]['name'] == 'stopC - stopB'
        assert response['lines'][0]['network']['id'] == 'network:additional_service'
        assert response['lines'][0]['commercial_mode']['id'] == 'commercial_mode:additional_service'
        assert response['lines'][0]['routes'][0]['id'] == 'route:stopC_stopB'
        assert response['lines'][0]['routes'][0]['name'] == 'stopC - stopB'
        assert response['lines'][0]['routes'][0]['direction']['id'] == 'stopB'
        assert response['lines'][0]['routes'][0]['direction_type'] == 'forward'

        # Check that objects created are linked in PT-Ref filter
        response = self.query_region(vj_filter_query)
        assert has_the_disruption(response, 'new_trip')
        assert len(response['vehicle_journeys']) == 1

        response = self.query_region(network_filter_query)
        assert len(response['networks']) == 1
        assert response['networks'][0]['name'] == 'additional service'

        # Check that no departure exist on stop_point stop_point:stopC for base_schedule
        departures = self.query_region(departure_query + '&data_freshness=base_schedule')
        assert len(departures['departures']) == 0

        # Check that departures on stop_point stop_point:stopC exists with disruption
        departures = self.query_region(departure_query + '&data_freshness=realtime')
        assert len(departures['disruptions']) == 1
        assert departures['disruptions'][0]['disruption_uri'] == 'new_trip'
        assert departures['departures'][0]['display_informations']['name'] == 'stopC - stopB'

        # Check that stop_schedule on line "line:stopC_stopB" and stop_point stop_point:stopC
        # exists with disruption
        stop_schedules = self.query_region(ss_on_line_query)
        assert len(stop_schedules['stop_schedules']) == 1
        assert stop_schedules['stop_schedules'][0]['links'][0]['id'] == 'line:stopC_stopB'
        assert len(stop_schedules['disruptions']) == 1
        assert stop_schedules['disruptions'][0]['uri'] == 'new_trip'
        assert len(stop_schedules['stop_schedules'][0]['date_times']) == 1
        assert stop_schedules['stop_schedules'][0]['date_times'][0]['data_freshness'] == 'realtime'

        # Check stop_schedules on stop_point stop_point:stopC for base_schedule
        # Date_times list is empty for both stop_schedules
        stop_schedules = self.query_region(ss_on_sp_query + '&data_freshness=base_schedule')
        assert len(stop_schedules['stop_schedules']) == 2
        assert stop_schedules['stop_schedules'][0]['links'][0]['type'] == 'line'
        assert stop_schedules['stop_schedules'][0]['links'][0]['id'] == 'D'
        assert len(stop_schedules['stop_schedules'][0]['date_times']) == 0
        assert stop_schedules['stop_schedules'][1]['links'][0]['type'] == 'line'
        assert stop_schedules['stop_schedules'][1]['links'][0]['id'] == 'line:stopC_stopB'
        assert len(stop_schedules['stop_schedules'][1]['date_times']) == 0

        # Check stop_schedules on stop_point stop_point:stopC for realtime
        # Date_times list is empty for line 'D' but not for the new line added
        stop_schedules = self.query_region(ss_on_sp_query + '&data_freshness=realtime')
        assert len(stop_schedules['stop_schedules']) == 2
        assert stop_schedules['stop_schedules'][0]['links'][0]['type'] == 'line'
        assert stop_schedules['stop_schedules'][0]['links'][0]['id'] == 'D'
        assert len(stop_schedules['stop_schedules'][0]['date_times']) == 0
        assert stop_schedules['stop_schedules'][1]['links'][0]['type'] == 'line'
        assert stop_schedules['stop_schedules'][1]['links'][0]['id'] == 'line:stopC_stopB'
        assert len(stop_schedules['stop_schedules'][1]['date_times']) == 1
        assert stop_schedules['stop_schedules'][1]['date_times'][0]['date_time'] == '20120614T080100'
        assert stop_schedules['stop_schedules'][1]['date_times'][0]['data_freshness'] == 'realtime'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddNewTripWithWrongPhysicalMode(MockKirinDisruptionsFixture):
    def test_add_new_trip_with_wrong_physical_mode(self):
        """
        1. send a disruption to create a new trip with physical_mode absent in kaken
        2. check of journey, disruption and PT-Ref objects to verify that no trip is added
        """
        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption, a new trip with 2 stop_times in realtime
        self.send_mock(
            "additional-trip",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
            physical_mode_id='physical_mode:Toto',  # this physical mode doesn't exist in kraken
        )

        # Check there is no new disruption
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before == len(disruptions_after['disruptions'])

        # / Journeys: as no trip on pt added, only direct walk.
        C_B_query = (
            "journeys?from={f}&to={to}&data_freshness=realtime&"
            "datetime={dt}&_current_datetime={dt}".format(
                f='stop_point:stopC', to='stop_point:stopB', dt='20120614T080000'
            )
        )
        response = self.query_region(C_B_query)
        assert not has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 1
        assert 'non_pt_walking' in response['journeys'][0]['tags']

        # Check that no vehicle_journey is added
        vj_query = 'vehicle_journeys/{vj}?_current_datetime={dt}'.format(
            vj='vehicle_journey:additional-trip:modified:0:new_trip', dt='20120614T080000'
        )
        response, status = self.query_region(vj_query, check=False)
        assert status == 404
        assert 'vehicle_journeys' not in response


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddNewTripWithoutPhysicalMode(MockKirinDisruptionsFixture):
    def test_add_new_trip_without_physical_mode(self):
        """
        1. send a disruption to create a new trip without physical_mode absent in kaken
        2. check physical_mode of journey
        """
        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption, a new trip with 2 stop_times in realtime
        self.send_mock(
            "additional-trip",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
        )

        # Check that a new disruption is added
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])

        C_B_query = (
            "journeys?from={f}&to={to}&data_freshness=realtime&"
            "datetime={dt}&_current_datetime={dt}".format(
                f='stop_point:stopC', to='stop_point:stopB', dt='20120614T080000'
            )
        )

        # Check that a PT journey exists with first physical_mode in the NTFS('Tramway')
        response = self.query_region(C_B_query)
        assert has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 2
        pt_journey = response['journeys'][0]
        assert 'non_pt_walking' not in pt_journey['tags']
        assert pt_journey['status'] == 'ADDITIONAL_SERVICE'
        assert pt_journey['sections'][0]['data_freshness'] == 'realtime'
        assert pt_journey['sections'][0]['display_informations']['commercial_mode'] == 'additional service'
        assert pt_journey['sections'][0]['display_informations']['physical_mode'] == 'Tramway'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinUpdateTripWithPhysicalMode(MockKirinDisruptionsFixture):
    def test_update_trip_with_physical_mode(self):
        """
        1. send a disruption with a physical_mode to update a trip
        2. check physical_mode of journey
        """
        # we have 7 vehicle_jouneys
        pt_response = self.query_region('vehicle_journeys')
        initial_nb_vehicle_journeys = len(pt_response['vehicle_journeys'])
        assert initial_nb_vehicle_journeys == 7

        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # physical_mode of base vehicle_journey
        pt_response = self.query_region(
            'vehicle_journeys/vehicle_journey:vjA/physical_modes?_current_datetime=20120614T1337'
        )
        assert len(pt_response['physical_modes']) == 1
        assert pt_response['physical_modes'][0]['name'] == 'Tramway'

        self.send_mock(
            "vjA",
            "20120614",
            'modified',
            [
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival=tstamp("20120614T080224"),
                    departure=tstamp("20120614T080225"),
                    arrival_delay=60 + 24,
                    departure_delay=60 + 25,
                    message='cow on tracks',
                ),
                UpdatedStopTime(
                    "stop_point:stopA",
                    arrival=tstamp("20120614T080400"),
                    departure=tstamp("20120614T080400"),
                    arrival_delay=3 * 60 + 58,
                    departure_delay=3 * 60 + 58,
                ),
            ],
            disruption_id='vjA_delayed',
            physical_mode_id='physical_mode:Bus',  # this physical mode exists in kraken
        )

        # Check that a new disruption is added
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])

        # A new vj is created
        pt_response = self.query_region('vehicle_journeys')
        assert len(pt_response['vehicle_journeys']) == (initial_nb_vehicle_journeys + 1)

        # physical_mode of the newly created vehicle_journey is the base vehicle_journey physical mode (Tramway)
        pt_response = self.query_region(
            'vehicle_journeys/vehicle_journey:vjA:modified:0:vjA_delayed/physical_modes'
        )
        assert len(pt_response['physical_modes']) == 1
        assert pt_response['physical_modes'][0]['name'] == 'Tramway'


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddTripWithHeadSign(MockKirinDisruptionsFixture):
    def test_add_trip_with_headsign(self):
        """
        1. send a disruption with a headsign to add a trip
        2. check that headsign is present in journey.section.display_informations
        """
        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption, a new trip with 2 stop_times in realtime
        self.send_mock(
            "additional-trip",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
            headsign='trip_headsign',
        )

        # Check that a new disruption is added
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])

        C_B_query = (
            "journeys?from={f}&to={to}&data_freshness=realtime&"
            "datetime={dt}&_current_datetime={dt}".format(
                f='stop_point:stopC', to='stop_point:stopB', dt='20120614T080000'
            )
        )

        # Check that a PT journey exists with trip_headsign in display_informations
        response = self.query_region(C_B_query)
        assert has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 2
        pt_journey = response['journeys'][0]
        assert pt_journey['status'] == 'ADDITIONAL_SERVICE'
        assert pt_journey['sections'][0]['data_freshness'] == 'realtime'
        assert pt_journey['sections'][0]['display_informations']['headsign'] == 'trip_headsign'


@dataset(MAIN_ROUTING_TEST_SETTING_NO_ADD)
class TestKirinAddNewTripBlocked(MockKirinDisruptionsFixture):
    def test_add_new_trip_blocked(self):
        """
        Disable realtime trip-add in Kraken
        1. send a disruption to create a new trip
        2. test that no journey is possible using this new trip
        3. test that no PT-Ref objects were created
        4. test that /pt_objects doesn't return objects
        5. test that PT-Ref filters find nothing
        6. test /departures and stop_schedules
        """
        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # New disruption, a new trip with 2 stop_times in realtime
        self.send_mock(
            "additional-trip",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
        )

        # Check there is no new disruption
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before == len(disruptions_after['disruptions'])

        # /journeys before (only direct walk)
        C_B_query = (
            "journeys?from={f}&to={to}&data_freshness=realtime&"
            "datetime={dt}&_current_datetime={dt}".format(
                f='stop_point:stopC', to='stop_point:stopB', dt='20120614T080000'
            )
        )
        response = self.query_region(C_B_query)
        assert not has_the_disruption(response, 'new_trip')
        self.is_valid_journey_response(response, C_B_query)
        assert len(response['journeys']) == 1
        assert 'non_pt_walking' in response['journeys'][0]['tags']

        # /pt_objects before
        ptobj_query = 'pt_objects?q={q}&_current_datetime={dt}'.format(q='adi', dt='20120614T080000')  # ++typo
        response = self.query_region(ptobj_query)
        assert 'pt_objects' not in response

        # Check that no vehicle_journey exists on the future realtime-trip
        vj_query = 'vehicle_journeys/{vj}?_current_datetime={dt}'.format(
            vj='vehicle_journey:additional-trip:modified:0:new_trip', dt='20120614T080000'
        )
        response, status = self.query_region(vj_query, check=False)
        assert status == 404
        assert 'vehicle_journeys' not in response

        # Check that no additional line exists
        line_query = 'lines/{l}?_current_datetime={dt}'.format(l='line:stopC_stopB', dt='20120614T080000')
        response, status = self.query_region(line_query, check=False)
        assert status == 404
        assert 'lines' not in response

        # Check that PT-Ref filter fails as no object exists
        vj_filter_query = 'commercial_modes/{cm}/vehicle_journeys?_current_datetime={dt}'.format(
            cm='commercial_mode:additional_service', dt='20120614T080000'
        )
        response, status = self.query_region(vj_filter_query, check=False)
        assert status == 404
        assert response['error']['message'] == 'ptref : Filters: Unable to find object'

        network_filter_query = 'vehicle_journeys/{vj}/networks?_current_datetime={dt}'.format(
            vj='vehicle_journey:additional-trip:modified:0:new_trip', dt='20120614T080000'
        )
        response, status = self.query_region(network_filter_query, check=False)
        assert status == 404
        assert response['error']['message'] == 'ptref : Filters: Unable to find object'

        # Check that no departure exist on stop_point stop_point:stopC
        departure_query = "stop_points/stop_point:stopC/departures?_current_datetime=20120614T080000"
        departures = self.query_region(departure_query)
        assert len(departures['departures']) == 0

        # Check that no stop_schedule exist on line:stopC_stopB and stop_point stop_point:stopC
        ss_query = (
            "stop_points/stop_point:stopC/lines/line:stopC_stopB/"
            "stop_schedules?_current_datetime=20120614T080000&data_freshness=realtime"
        )
        stop_schedules, status = self.query_region(ss_query, check=False)
        assert status == 404
        assert len(stop_schedules['stop_schedules']) == 0


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddNewTripPresentInNavitiaTheSameDay(MockKirinDisruptionsFixture):
    def test_add_new_trip_present_in_navitia_the_same_day(self):

        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # The vehicle_journey vjA is present in navitia
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')

        assert len(pt_response['vehicle_journeys']) == 1
        assert len(pt_response['disruptions']) == 0

        # New disruption, a new trip with vehicle_journey id = vjA and having 2 stop_times in realtime
        self.send_mock(
            "vjA",
            "20120614",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080100"),
                    departure=tstamp("20120614T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120614T080102"),
                    departure=tstamp("20120614T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
        )

        # Check that there should not be a new disruption
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before == len(disruptions_after['disruptions'])


@dataset(MAIN_ROUTING_TEST_SETTING)
class TestKirinAddNewTripPresentInNavitiaWithAShift(MockKirinDisruptionsFixture):
    def test_add_new_trip_present_in_navitia_with_a_shift(self):

        disruption_query = 'disruptions?_current_datetime={dt}'.format(dt='20120614T080000')
        disruptions_before = self.query_region(disruption_query)
        nb_disruptions_before = len(disruptions_before['disruptions'])

        # The vehicle_journey vjA is present in navitia
        pt_response = self.query_region('vehicle_journeys/vehicle_journey:vjA?_current_datetime=20120614T1337')

        assert len(pt_response['vehicle_journeys']) == 1
        assert len(pt_response['disruptions']) == 0

        # New disruption, a new trip with meta vehicle journey id = vjA and having 2 stop_times in realtime
        self.send_mock(
            "vjA",
            "20120620",
            'added',
            [
                UpdatedStopTime(
                    "stop_point:stopC",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120620T080100"),
                    departure=tstamp("20120620T080100"),
                    message='on time',
                ),
                UpdatedStopTime(
                    "stop_point:stopB",
                    arrival_delay=0,
                    departure_delay=0,
                    is_added=True,
                    arrival=tstamp("20120620T080102"),
                    departure=tstamp("20120620T080102"),
                ),
            ],
            disruption_id='new_trip',
            effect='additional_service',
        )

        # The new trip is accepted because, it is not the same day of the base vj
        # So a disruption is added
        disruptions_after = self.query_region(disruption_query)
        assert nb_disruptions_before + 1 == len(disruptions_after['disruptions'])


def make_mock_kirin_item(
    vj_id,
    date,
    status='canceled',
    new_stop_time_list=[],
    disruption_id=None,
    effect=None,
    physical_mode_id=None,
    headsign=None,
):
    feed_message = gtfs_realtime_pb2.FeedMessage()
    feed_message.header.gtfs_realtime_version = '1.0'
    feed_message.header.incrementality = gtfs_realtime_pb2.FeedHeader.DIFFERENTIAL
    feed_message.header.timestamp = 0

    entity = feed_message.entity.add()
    entity.id = disruption_id or "{}".format(uuid.uuid1())
    trip_update = entity.trip_update

    trip = trip_update.trip
    trip.trip_id = vj_id
    trip.start_date = date
    trip.Extensions[kirin_pb2.contributor] = rt_topic
    if headsign:
        trip_update.Extensions[kirin_pb2.headsign] = headsign
    if physical_mode_id:
        trip_update.vehicle.Extensions[kirin_pb2.physical_mode_id] = physical_mode_id
    if effect == 'unknown':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.UNKNOWN_EFFECT
    elif effect == 'modified':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.MODIFIED_SERVICE
    elif effect == 'delayed':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.SIGNIFICANT_DELAYS
    elif effect == 'detour':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.DETOUR
    elif effect == 'reduced_service':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.REDUCED_SERVICE
    elif effect == 'additional_service':
        trip_update.Extensions[kirin_pb2.effect] = gtfs_realtime_pb2.Alert.ADDITIONAL_SERVICE

    if status == 'canceled':
        # TODO: remove this deprecated code (for retrocompatibility with Kirin < 0.8.0 only)
        trip.schedule_relationship = gtfs_realtime_pb2.TripDescriptor.CANCELED
    elif status in ['modified', 'added']:
        # TODO: remove this deprecated code (for retrocompatibility with Kirin < 0.8.0 only)
        if status == 'modified':
            trip.schedule_relationship = gtfs_realtime_pb2.TripDescriptor.SCHEDULED
        elif status == 'added':
            trip.schedule_relationship = gtfs_realtime_pb2.TripDescriptor.ADDED

        for st in new_stop_time_list:
            stop_time_update = trip_update.stop_time_update.add()
            stop_time_update.stop_id = st.stop_id
            stop_time_update.arrival.time = st.arrival
            stop_time_update.arrival.delay = st.arrival_delay
            stop_time_update.departure.time = st.departure
            stop_time_update.departure.delay = st.departure_delay

            def get_stop_time_status(is_skipped=False, is_added=False, is_detour=False):
                if is_skipped:
                    if is_detour:
                        return kirin_pb2.DELETED_FOR_DETOUR
                    return kirin_pb2.DELETED
                if is_added:
                    if is_detour:
                        return kirin_pb2.ADDED_FOR_DETOUR
                    return kirin_pb2.ADDED
                return kirin_pb2.SCHEDULED

            stop_time_update.arrival.Extensions[kirin_pb2.stop_time_event_status] = get_stop_time_status(
                st.arrival_skipped, st.is_added, st.is_detour
            )
            stop_time_update.departure.Extensions[kirin_pb2.stop_time_event_status] = get_stop_time_status(
                st.departure_skipped, st.is_added, st.is_detour
            )
            if st.message:
                stop_time_update.Extensions[kirin_pb2.stoptime_message] = st.message
    else:
        # TODO
        pass

    return feed_message.SerializeToString()

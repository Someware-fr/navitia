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

import logging
import pybreaker
import zmq

from datetime import datetime, timedelta
import flask
import six

from jormungandr import app
from jormungandr.transient_socket import TransientSocket
from jormungandr.exceptions import DeadSocketException
from navitiacommon import response_pb2, request_pb2, type_pb2


class ZmqSocket(TransientSocket):
    def __init__(
        self,
        name,
        zmq_context,
        zmq_socket,
        zmq_socket_type,
        timeout,
        socket_ttl=app.config.get(str('ZMQ_SOCKET_TTL_SECONDS'), 10),
    ):

        if zmq_socket_type == 'persistent':
            socket_ttl = float('inf')

        super(ZmqSocket, self).__init__(
            name=name, zmq_context=zmq_context, zmq_socket=zmq_socket, socket_ttl=socket_ttl
        )
        self.timeout = timeout
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=app.config.get(str('CIRCUIT_BREAKER_MAX_INSTANCE_FAIL'), 5),
            reset_timeout=app.config.get(str('CIRCUIT_BREAKER_INSTANCE_TIMEOUT_S'), 60),
        )

    def _send_and_receive(self, request, quiet=False, **kwargs):
        deadline = datetime.utcnow() + timedelta(milliseconds=self.timeout * 1000)
        request.deadline = deadline.strftime('%Y%m%dT%H%M%S,%f')

        if 'request_id' in kwargs and kwargs['request_id']:
            request.request_id = kwargs['request_id']
        else:
            try:
                request.request_id = flask.request.id
            except RuntimeError:
                # we aren't in a flask context, so there is no request
                if 'flask_request_id' in kwargs and kwargs['flask_request_id']:
                    request.request_id = kwargs['flask_request_id']

        pb = self.call(
            request.SerializeToString(), self.timeout, debug_cb=lambda: six.text_type(request), quiet=quiet
        )
        resp = response_pb2.Response()
        resp.ParseFromString(pb)
        return resp

    def send_and_receive(self, *args, **kwargs):
        """
        encapsulate all call to kraken in a circuit breaker, this way we don't lose time calling dead instance
        """
        try:
            return self.breaker.call(self._send_and_receive, *args, **kwargs)
        except pybreaker.CircuitBreakerError:
            raise DeadSocketException(self.name, self._zmq_socket)

    def clean_up_zmq_sockets(self):
        for socket in self._sockets:
            socket.setsockopt(zmq.LINGER, 0)
            socket.close()

    @staticmethod
    def is_zmq_socket():
        return True


def get_crow_fly(
    pt_planner,
    origin,
    streetnetwork_mode,
    max_duration,
    max_nb_crowfly,
    object_type=type_pb2.STOP_POINT,
    filter=None,
    stop_points_nearby_duration=300,
    request_id=None,
    depth=2,
    forbidden_uris=[],
    allowed_id=[],
    **kwargs
):
    logger = logging.getLogger(__name__)
    # Getting stop_points or stop_areas using crow fly
    # the distance of crow fly is defined by the mode speed and max_duration
    req = request_pb2.Request()
    req.requested_api = type_pb2.places_nearby
    req.places_nearby.uri = origin
    req.places_nearby.distance = kwargs.get(streetnetwork_mode, kwargs.get("walking")) * max_duration
    req.places_nearby.depth = depth
    req.places_nearby.count = max_nb_crowfly
    req.places_nearby.start_page = 0
    req.disable_feedpublisher = True
    req.places_nearby.types.append(object_type)

    allowed_id_filter = ''
    if allowed_id is not None:
        allowed_id_count = len(allowed_id)
        if allowed_id_count > 0:
            poi_ids = ('poi.id={}'.format(uri) for uri in allowed_id)
            allowed_id_items = '  or  '.join(poi_ids)

            # Format the filter for all allowed_ids uris
            if allowed_id_count >= 1:
                allowed_id_filter = ' and ({})'.format(allowed_id_items)

    # We implement filter only for poi with poi_type.uri=poi_type:amenity:parking
    if filter is not None:
        req.places_nearby.filter = filter + allowed_id_filter
    if streetnetwork_mode == "car":
        req.places_nearby.stop_points_nearby_radius = kwargs.get("walking", 1.11) * stop_points_nearby_duration
        req.places_nearby.depth = 1
    if forbidden_uris is not None:
        for uri in forbidden_uris:
            req.places_nearby.forbidden_uris.append(uri)
    res = pt_planner.send_and_receive(req, request_id=request_id)
    if len(res.feed_publishers) != 0:
        logger.error("feed publisher not empty: expect performance regression!")
    return res.places_nearby


def get_odt_stop_points(pt_planner, coord, request_id):
    req = request_pb2.Request()
    req.requested_api = type_pb2.odt_stop_points
    req.coord.lon = coord.lon
    req.coord.lat = coord.lat
    return pt_planner.send_and_receive(req, request_id=request_id).stop_points

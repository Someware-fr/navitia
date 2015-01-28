# -*- coding: utf-8 -*-
## File autogenerated by SQLAutoCode
## see http://code.google.com/p/sqlautocode/

from sqlalchemy import *
from sqlalchemy.dialects.postgresql import *
from geoalchemy2 import Geography
from models import metadata

object_type = Table('object_type', metadata,*[
    Column('id', INTEGER(), primary_key=True, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


connection_kind = Table('connection_kind', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


odt_type = Table('odt_type', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


meta_vj = Table('meta_vj', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


contributor = Table('contributor', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


commercial_mode = Table('commercial_mode', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


parameters = Table('parameters', metadata,*[
    Column('beginning_date', DATE(), primary_key=False),
    Column('end_date', DATE(), primary_key=False),
    Column('timezone', TEXT(), primary_key=False),
    Column('shape', Geography(geometry_type='MULTIPOLYGON', srid=4326, spatial_index=False), primary_key=False),
    Column('shape_computed', BOOLEAN(), primary_key=False, default=text(u'true')),
    ],
    schema='navitia')


company = Table('company', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('address_name', TEXT(), primary_key=False),
    Column('address_number', TEXT(), primary_key=False),
    Column('address_type_name', TEXT(), primary_key=False),
    Column('phone_number', TEXT(), primary_key=False),
    Column('mail', TEXT(), primary_key=False),
    Column('website', TEXT(), primary_key=False),
    Column('fax', TEXT(), primary_key=False),],
    schema='navitia')


physical_mode = Table('physical_mode', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('co2_emission', FLOAT(), primary_key=False, nullable=False, default=0)],
    schema='navitia')


validity_pattern = Table('validity_pattern', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('days', BIT(length=400, varying=True), primary_key=False, nullable=False),],
    schema='navitia')


rel_metavj_vj = Table('rel_metavj_vj', metadata,*[
    Column('meta_vj', BIGINT(), primary_key=False),
    Column('vehicle_journey', BIGINT(), primary_key=False),
    Column('vj_class', ENUM(u'Theoric', u'Adapted', u'RealTime', name='vj_classification'), primary_key=False, nullable=False),
    ForeignKeyConstraint(['vehicle_journey'], [u'navitia.vehicle_journey.id'], name=u'rel_metavj_vj_vehicle_journey_fkey'),
    ForeignKeyConstraint(['meta_vj'], [u'navitia.meta_vj.id'], name=u'rel_metavj_vj_meta_vj_fkey'),
    ],
    schema='navitia')

associated_calendar = Table('associated_calendar', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".associated_calendar_id_seq\'::regclass)')),
    Column('calendar_id', BIGINT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['calendar_id'], [u'navitia.calendar.id'], name=u'associated_calendar_calendar_fkey'),
    ],
    schema='navitia')


associated_exception_date = Table('associated_exception_date', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".associated_exception_date_id_seq\'::regclass)')),
    Column('datetime', DATE(), primary_key=False, nullable=False),
    Column('type_ex', ENUM(u'Add', u'Sub', name='associated_exception_type'), primary_key=False, nullable=False),
    Column('associated_calendar_id', BIGINT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['associated_calendar_id'], [u'navitia.associated_calendar.id'], name=u'associated_exception_date_associated_calendar_fkey'),
    ],
    schema='navitia')


rel_metavj_associated_calendar = Table('rel_metavj_associated_calendar', metadata,*[
    Column('meta_vj_id', BIGINT(), primary_key=False),
    Column('associated_calendar_id', BIGINT(), primary_key=False),
    ForeignKeyConstraint(['meta_vj_id'], [u'navitia.meta_vj.id'], name=u'rel_metavj_associated_calendar_meta_vj_fkey'),
    ForeignKeyConstraint(['associated_calendar_id'], [u'navitia.associated_calendar.id'], name=u'rel_metavj_associated_calendar_associated_calendar_fkey')],
    schema='navitia')


rel_line_company = Table('rel_line_company', metadata,*[
    Column('line_id', BIGINT(), primary_key=True, nullable=False),
    Column('company_id', BIGINT(), primary_key=True, nullable=False),
    ForeignKeyConstraint(['line_id'], [u'navitia.line.id'], name=u'rel_line_company_line_id_fkey'),
    ForeignKeyConstraint(['company_id'], [u'navitia.company.id'], name=u'rel_line_company_company_id_fkey'),],
    schema='navitia')


route = Table('route', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('line_id', BIGINT(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('shape', Geography(geometry_type='MULTILINESTRING', srid=4326, spatial_index=False), primary_key=False),
    ForeignKeyConstraint(['line_id'], [u'navitia.line.id'], name=u'route_line_id_fkey'),],
    schema='navitia')


vehicle_properties = Table('vehicle_properties', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".vehicle_properties_id_seq\'::regclass)')),
    Column('wheelchair_accessible', BOOLEAN(), primary_key=False, nullable=False),
    Column('bike_accepted', BOOLEAN(), primary_key=False, nullable=False),
    Column('air_conditioned', BOOLEAN(), primary_key=False, nullable=False),
    Column('visual_announcement', BOOLEAN(), primary_key=False, nullable=False),
    Column('audible_announcement', BOOLEAN(), primary_key=False, nullable=False),
    Column('appropriate_escort', BOOLEAN(), primary_key=False, nullable=False),
    Column('appropriate_signage', BOOLEAN(), primary_key=False, nullable=False),
    Column('school_vehicle', BOOLEAN(), primary_key=False, nullable=False),
    ],
    schema='navitia')


network = Table('network', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('sort', INTEGER(), primary_key=False, nullable=False, default=text(u'2147483647')),
    Column('website', TEXT(), primary_key=False),],
    schema='navitia')


origin_destination = Table('origin_destination', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('origin_id', TEXT(), primary_key=False, nullable=False),
    Column('origin_mode', ENUM(u'Zone', u'StopArea', u'Mode', name='fare_od_mode'), primary_key=False, nullable=False),
    Column('destination_id', TEXT(), primary_key=False, nullable=False),
    Column('destination_mode', ENUM(u'Zone', u'StopArea', u'Mode', name='fare_od_mode'), primary_key=False, nullable=False),
    ],
    schema='navitia')


ticket = Table('ticket', metadata,*[
    Column('ticket_key', TEXT(), primary_key=True, nullable=False),
    Column('ticket_title', TEXT(), primary_key=False),
    Column('ticket_comment', TEXT(), primary_key=False),],
    schema='navitia')


od_ticket = Table('od_ticket', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('od_id', BIGINT(), primary_key=False, nullable=False),
    Column('ticket_id', TEXT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['ticket_id'], [u'navitia.ticket.ticket_key'], name=u'od_ticket_ticket_id_fkey'),
    ForeignKeyConstraint(['od_id'], [u'navitia.origin_destination.id'], name=u'od_ticket_od_id_fkey'),],
    schema='navitia')


connection_type = Table('connection_type', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),],
    schema='navitia')


properties = Table('properties', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('wheelchair_boarding', BOOLEAN(), primary_key=False, nullable=False),
    Column('sheltered', BOOLEAN(), primary_key=False, nullable=False),
    Column('elevator', BOOLEAN(), primary_key=False, nullable=False),
    Column('escalator', BOOLEAN(), primary_key=False, nullable=False),
    Column('bike_accepted', BOOLEAN(), primary_key=False, nullable=False),
    Column('bike_depot', BOOLEAN(), primary_key=False, nullable=False),
    Column('visual_announcement', BOOLEAN(), primary_key=False, nullable=False),
    Column('audible_announcement', BOOLEAN(), primary_key=False, nullable=False),
    Column('appropriate_escort', BOOLEAN(), primary_key=False, nullable=False),
    Column('appropriate_signage', BOOLEAN(), primary_key=False, nullable=False),
    ],
    schema='navitia')


connection = Table('connection', metadata,*[
    Column('departure_stop_point_id', BIGINT(), primary_key=True, nullable=False),
    Column('destination_stop_point_id', BIGINT(), primary_key=True, nullable=False),
    Column('connection_type_id', BIGINT(), primary_key=False, nullable=False),
    Column('properties_id', BIGINT(), primary_key=False),
    Column('duration', INTEGER(), primary_key=False, nullable=False),
    Column('max_duration', INTEGER(), primary_key=False, nullable=False),
    Column('display_duration', INTEGER(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['properties_id'], [u'navitia.properties.id'], name=u'connection_properties_id_fkey'),
    ForeignKeyConstraint(['destination_stop_point_id'], [u'navitia.stop_point.id'], name=u'connection_destination_stop_point_id_fkey'),
    ForeignKeyConstraint(['departure_stop_point_id'], [u'navitia.stop_point.id'], name=u'connection_departure_stop_point_id_fkey'),
    ForeignKeyConstraint(['connection_type_id'], [u'navitia.connection_type.id'], name=u'connection_connection_type_id_fkey'),],
    schema='navitia')


journey_pattern = Table('journey_pattern', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('route_id', BIGINT(), primary_key=False, nullable=False),
    Column('physical_mode_id', BIGINT(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('is_frequence', BOOLEAN(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['route_id'], [u'navitia.route.id'], name=u'journey_pattern_route_id_fkey'),
    ForeignKeyConstraint(['physical_mode_id'], [u'navitia.physical_mode.id'], name=u'journey_pattern_physical_mode_id_fkey'),],
    schema='navitia')


vehicle_journey = Table('vehicle_journey', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('adapted_validity_pattern_id', BIGINT(), primary_key=False, nullable=False),
    Column('validity_pattern_id', BIGINT(), primary_key=False),
    Column('company_id', BIGINT(), primary_key=False, nullable=False),
    Column('journey_pattern_id', BIGINT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('odt_message', TEXT(), primary_key=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('odt_type_id', BIGINT(), primary_key=False),
    Column('vehicle_properties_id', BIGINT(), primary_key=False),
    Column('theoric_vehicle_journey_id', BIGINT(), primary_key=False),
    Column('previous_vehicle_journey_id', BIGINT(), primary_key=False),
    Column('next_vehicle_journey_id', BIGINT(), primary_key=False),
    Column('start_time', INTEGER(), primary_key=False),
    Column('end_time', INTEGER(), primary_key=False),
    Column('headway_sec', INTEGER(), primary_key=False),
    Column('utc_to_local_offset', INTEGER(), primary_key=False),
    Column('is_frequency', BOOLEAN(), primary_key=False),
    ForeignKeyConstraint(['vehicle_properties_id'], [u'navitia.vehicle_properties.id'], name=u'vehicle_journey_vehicle_properties_id_fkey'),
    ForeignKeyConstraint(['validity_pattern_id'], [u'navitia.validity_pattern.id'], name=u'vehicle_journey_validity_pattern_id_fkey'),
    ForeignKeyConstraint(['previous_vehicle_journey_id'], [u'navitia.vehicle_journey.id'], name=u'vehicle_journey_previous_vehicle_journey_id_fkey'),
    ForeignKeyConstraint(['next_vehicle_journey_id'], [u'navitia.vehicle_journey.id'], name=u'vehicle_journey_next_vehicle_journey_id_fkey'),
    ForeignKeyConstraint(['journey_pattern_id'], [u'navitia.journey_pattern.id'], name=u'vehicle_journey_journey_pattern_id_fkey'),
    ForeignKeyConstraint(['adapted_validity_pattern_id'], [u'navitia.validity_pattern.id'], name=u'vehicle_journey_adapted_validity_pattern_id_fkey'),
    ForeignKeyConstraint(['company_id'], [u'navitia.company.id'], name=u'vehicle_journey_company_id_fkey'),
    ForeignKeyConstraint(['theoric_vehicle_journey_id'], [u'navitia.vehicle_journey.id'], name=u'vehicle_journey_theoric_vehicle_journey_id_fkey'),],
    schema='navitia')


stop_point = Table('stop_point', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('properties_id', BIGINT(), primary_key=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('coord', Geography(geometry_type='POINT', srid=4326, spatial_index=False), primary_key=False),
    Column('fare_zone', INTEGER(), primary_key=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('stop_area_id', BIGINT(), primary_key=False, nullable=False),
    Column('platform_code', TEXT(), primary_key=False),
    ForeignKeyConstraint(['properties_id'], [u'navitia.properties.id'], name=u'stop_point_properties_id_fkey'),
    ForeignKeyConstraint(['stop_area_id'], [u'navitia.stop_area.id'], name=u'stop_point_stop_area_id_fkey'),],
    schema='navitia')


stop_time = Table('stop_time', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".stop_time_id_seq\'::regclass)')),
    Column('vehicle_journey_id', BIGINT(), primary_key=False, nullable=False),
    Column('journey_pattern_point_id', BIGINT(), primary_key=False, nullable=False),
    Column('arrival_time', INTEGER(), primary_key=False),
    Column('departure_time', INTEGER(), primary_key=False),
    Column('local_traffic_zone', INTEGER(), primary_key=False),
    Column('odt', BOOLEAN(), primary_key=False, nullable=False),
    Column('pick_up_allowed', BOOLEAN(), primary_key=False, nullable=False),
    Column('drop_off_allowed', BOOLEAN(), primary_key=False, nullable=False),
    Column('is_frequency', BOOLEAN(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('date_time_estimated', BOOLEAN(), primary_key=False, nullable=False, default=text(u'false')),
    Column('properties_id', BIGINT(), primary_key=False),
    ForeignKeyConstraint(['vehicle_journey_id'], [u'navitia.vehicle_journey.id'], name=u'stop_time_vehicle_journey_id_fkey'),
    ForeignKeyConstraint(['properties_id'], [u'navitia.properties.id'], name=u'stop_time_properties_id_fkey'),
    ForeignKeyConstraint(['journey_pattern_point_id'], [u'navitia.journey_pattern_point.id'], name=u'stop_time_journey_pattern_point_id_fkey'),],
    schema='navitia')


journey_pattern_point = Table('journey_pattern_point', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('journey_pattern_id', BIGINT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('order', INTEGER(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('stop_point_id', BIGINT(), primary_key=False, nullable=False),
    Column('shape_from_prev', Geography(geometry_type='LINESTRING', srid=4326, spatial_index=False), primary_key=False),
    ForeignKeyConstraint(['stop_point_id'], [u'navitia.stop_point.id'], name=u'journey_pattern_point_stop_point_id_fkey'),
    ForeignKeyConstraint(['journey_pattern_id'], [u'navitia.journey_pattern.id'], name=u'journey_pattern_point_journey_pattern_id_fkey'),],
    schema='navitia')


period = Table('period', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".period_id_seq\'::regclass)')),
    Column('calendar_id', BIGINT(), primary_key=False, nullable=False),
    Column('begin_date', DATE(), primary_key=False, nullable=False),
    Column('end_date', DATE(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['calendar_id'], [u'navitia.calendar.id'], name=u'period_calendar_id_fkey'),],
    schema='navitia')


week_pattern = Table('week_pattern', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".week_pattern_id_seq\'::regclass)')),
    Column('monday', BOOLEAN(), primary_key=False, nullable=False),
    Column('tuesday', BOOLEAN(), primary_key=False, nullable=False),
    Column('wednesday', BOOLEAN(), primary_key=False, nullable=False),
    Column('thursday', BOOLEAN(), primary_key=False, nullable=False),
    Column('friday', BOOLEAN(), primary_key=False, nullable=False),
    Column('saturday', BOOLEAN(), primary_key=False, nullable=False),
    Column('sunday', BOOLEAN(), primary_key=False, nullable=False),
    ],
    schema='navitia')


exception_date = Table('exception_date', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".exception_date_id_seq\'::regclass)')),
    Column('datetime', DATE(), primary_key=False, nullable=False),
    Column('type_ex', ENUM(u'Add', u'Sub', name='exception_type'), primary_key=False, nullable=False),
    Column('calendar_id', BIGINT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['calendar_id'], [u'navitia.calendar.id'], name=u'exception_date_calendar_id_fkey'),
    ],
    schema='navitia')


rel_calendar_line = Table('rel_calendar_line', metadata,*[
    Column('calendar_id', BIGINT(), primary_key=True, nullable=False),
    Column('line_id', BIGINT(), primary_key=True, nullable=False),
    ForeignKeyConstraint(['line_id'], [u'navitia.line.id'], name=u'rel_calendar_line_line_id_fkey'),
    ForeignKeyConstraint(['calendar_id'], [u'navitia.calendar.id'], name=u'rel_calendar_line_calendar_id_fkey'),],
    schema='navitia')


line = Table('line', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('network_id', BIGINT(), primary_key=False, nullable=False),
    Column('commercial_mode_id', BIGINT(), primary_key=False, nullable=False),
    Column('comment', TEXT(), primary_key=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('code', TEXT(), primary_key=False),
    Column('color', TEXT(), primary_key=False),
    Column('sort', INTEGER(), primary_key=False, nullable=False, default=text(u'2147483647')),
    Column('shape', Geography(geometry_type='MULTILINESTRING', srid=4326, spatial_index=False), primary_key=False),
    ForeignKeyConstraint(['commercial_mode_id'], [u'navitia.commercial_mode.id'], name=u'line_commercial_mode_id_fkey'),
    ForeignKeyConstraint(['network_id'], [u'navitia.network.id'], name=u'line_network_id_fkey'),],
    schema='navitia')


calendar = Table('calendar', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False, default=text(u'nextval(\'"navitia".calendar_id_seq\'::regclass)')),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('week_pattern_id', BIGINT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['week_pattern_id'], [u'navitia.week_pattern.id'], name=u'calendar_week_pattern_id_fkey'),],
    schema='navitia')


transition = Table('transition', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('before_change', TEXT(), primary_key=False, nullable=False),
    Column('after_change', TEXT(), primary_key=False, nullable=False),
    Column('start_trip', TEXT(), primary_key=False, nullable=False),
    Column('end_trip', TEXT(), primary_key=False, nullable=False),
    Column('global_condition', ENUM(u'nothing', u'exclusive', u'with_changes', name='fare_transition_condition'), primary_key=False, nullable=False),
    Column('ticket_id', TEXT(), primary_key=False),
    ForeignKeyConstraint(['ticket_id'], [u'navitia.ticket.ticket_key'], name=u'transition_ticket_id_fkey'),
    ],
    schema='navitia')


dated_ticket = Table('dated_ticket', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('ticket_id', TEXT(), primary_key=False),
    Column('valid_from', DATE(), primary_key=False, nullable=False),
    Column('valid_to', DATE(), primary_key=False, nullable=False),
    Column('ticket_price', INTEGER(), primary_key=False, nullable=False),
    Column('comments', TEXT(), primary_key=False),
    Column('currency', TEXT(), primary_key=False),
    ForeignKeyConstraint(['ticket_id'], [u'navitia.ticket.ticket_key'], name=u'dated_ticket_ticket_id_fkey'),],
    schema='navitia')


admin_stop_area = Table('admin_stop_area', metadata,*[
    Column('admin_id', TEXT(), primary_key=False, nullable=False),
    Column('stop_area_id', BIGINT(), primary_key=False, nullable=False),
    ForeignKeyConstraint(['stop_area_id'], [u'navitia.stop_area.id'], name=u'admin_stop_area_stop_area_id_fkey'),],
    schema='navitia')


stop_area = Table('stop_area', metadata,*[
    Column('id', BIGINT(), primary_key=True, nullable=False),
    Column('properties_id', BIGINT(), primary_key=False),
    Column('uri', TEXT(), primary_key=False, nullable=False),
    Column('external_code', TEXT(), primary_key=False, nullable=False),
    Column('name', TEXT(), primary_key=False, nullable=False),
    Column('coord', Geography(geometry_type='POINT', srid=4326, spatial_index=False), primary_key=False),
    Column('comment', TEXT(), primary_key=False),
    Column('visible', BOOLEAN(), primary_key=False, nullable=False, default=text(u'true')),
    Column('timezone', TEXT(), primary_key=False),
    ForeignKeyConstraint(['properties_id'], [u'navitia.properties.id'], name=u'stop_area_properties_id_fkey'),],
    schema='navitia')


# -----------------------------------------------------------
# Example to show how data is integrated into the IoTCrawler framework
#
# (C) 2020 Thorben Iggena
# -----------------------------------------------------------

from json import JSONDecodeError

import pandas
import json
import threading
import requests
import dateutil.parser
import dateutil.tz

# Configuration stuff

# Broker addresses, if more than one address data will be sent to multiple brokers
BROKERS = []    #["155.54.95.248:9090"]

# Option to send data to another callback interface, e.g. for debugging or working without a broker
SEND_LOCAL = True
LOCAL_URL = 'http://localhost:8081/semanticenrichment/callback'

# If enabled prints ngsi-ld messages while sending to broker
PRINT_NGSI = True

# This example assumes data structured as shwon in 'cityprobe_example.json' file
# Field within the cityprobe data that is used as an 'identifier' for all entityids in ngsi-ld
IDENTIFIER = 'deviceid'

# These are the data fields within the example data. As the iotcrawler information model is build like '1 platform with
# x sensors each having 1 stream' we will build one sensor and stream for each of them.
FIELDS = ['battery', 'temperature', 'noise', 'CO', 'PM10', 'rain', 'humidity', 'illuminance', 'pressure', 'PM2.5',
          'NO2']

# The available metadata for some of the FIELDS.
META = {
    'updateinterval': 10,
    'unit': 'seconds',
    'humidity': {'min': 0.0, 'max': 100.0, 'valuetype': 'float'},
    'battery': {'min': 0.0, 'max': 100.0, 'valuetype': 'float'},
    'temperature': {'min': -30.0, 'max': 80.0, 'valuetype': 'float'}
}

# Headers used for requests to ngsi-ld broker.
headers = {}
headers.update({'content-type': 'application/ld+json'})
headers.update({'accept': 'application/json'})


def send_message(location, data):
    """Takes location as [latitudy, longitude] and the related 'record' entry from a city probe data set. Builds all
    neccessary information model classes (e.g. platform, sensor, etc.) and sends them to the broker. """
    try:
        platform = platform_build(data, location)
        sensors = []
        observations = []
        streams = []
        observableproperties = []

        for field in FIELDS:
            observableproperty = observableproperty_build(field, data)

            sensor = sensor_build(data, field, location)
            sensor_addmetainformation(sensor, field)
            sensor_addplatform(sensor, platform)
            platform_addsensor(platform, sensor)

            stream = stream_build(data, field)
            stream_addsensor(stream, sensor)

            observation = observation_build(data, field)
            observation_addstream(observation, stream)
            observation_addsensor(observation, sensor)
            observation_addobservableproperty(observation, observableproperty)

            sensor_addobservableproperty(sensor, observableproperty)
            sensor_addobservation(sensor, observation)

            sensors.append(sensor)
            streams.append(stream)
            observations.append(observation)
            observableproperties.append(observableproperty)

        # create the entities in MDR
        create_ngsi_entity(platform)
        if SEND_LOCAL:
            send_local(platform)

        for sensor in sensors:
            create_ngsi_entity(sensor)
            if SEND_LOCAL:
                send_local(sensor)

        for stream in streams:
            create_ngsi_entity(stream)
            if SEND_LOCAL:
                send_local(stream)

        for observableproperty in observableproperties:
            create_ngsi_entity(observableproperty)
            if SEND_LOCAL:
                send_local(observableproperty)

        for observation in observations:
            create_ngsi_entity(observation)
            if SEND_LOCAL:
                send_local(observation)

    except (UnicodeDecodeError, JSONDecodeError) as e:
        print("Message not well formated:", str(e))


def sensor_addmetainformation(sensor, field):
    """Adds avilable metadata for a field to a given sensor"""
    if field in META:
        if 'min' in META[field]:
            sensor['qoi:min']['value'] = META[field]['min']
        if 'max' in META[field]:
            sensor['qoi:max']['value'] = META[field]['max']
        if 'valuetype' in META[field]:
            sensor['qoi:valuetype']['value'] = META[field]['valuetype']

    if 'updateinterval' in META:
        sensor['qoi:updateinterval']['value'] = META['updateinterval']
        if 'unit' in META:
            sensor['qoi:updateinterval']['qoi:unit']['value'] = META['unit']


def stream_build(data, field):
    """Creates a new stream by loading the dummy stream file and setting its name."""
    with open("json/stream.json") as jFile:
        name = data[IDENTIFIER] + ":" + field
        stream = json.load(jFile)
        stream['id'] = stream['id'] + name
        return stream


def stream_addsensor(stream, sensor):
    """Adds a sensor to a stream."""
    stream['iot-stream:generatedBy']['object'] = sensor['id']


def observableproperty_build(field, data):
    """Creates a new observable property."""
    with open('json/observableproperty.json') as jFile:
        observableproperty = json.load(jFile)
        observableproperty['id'] = observableproperty['id'] + data[IDENTIFIER] + ":" + field
        observableproperty['rdfs:label']['value'] = field.lower()
        return observableproperty


def platform_build(data, coordinates=None):
    """Creates a new platform."""
    with open('json/platform.json') as jFile:
        platform = json.load(jFile)
        platform['id'] = platform['id'] + data[IDENTIFIER]
        if coordinates:
            platform['location']['value']['coordinates'] = coordinates
        return platform


def platform_addsensor(platform, sensor):
    """Adds a sensor to a given platform."""
    i = str(sum([1 for k, v in platform.items() if k.startswith('sosa:hosts')]) + 1)
    platform['sosa:hosts#' + i] = {}
    platform['sosa:hosts#' + i]['type'] = 'Relationship'
    platform['sosa:hosts#' + i]['object'] = sensor['id']


def sensor_build(data, field, coordinates=None):
    """Creates a new sensor."""
    with open('json/sensor.json') as jFile:
        sensor = json.load(jFile)
        sensor['id'] = sensor['id'] + data[IDENTIFIER] + ":" + field
        if coordinates:
            sensor['location']['value']['coordinates'] = coordinates
        return sensor


def sensor_addobservation(sensor, observation):
    """Adds an observation to a sensor."""
    sensor['sosa:madeObservation']['object'] = observation['id']


def sensor_addobservableproperty(sensor, observableproperty):
    """Adds an obseravable property to a sensor."""
    sensor['sosa:observes']['object'] = observableproperty['id']


def sensor_addplatform(sensor, platform):
    """Adds a platform to a sensor."""
    sensor['sosa:isHostedBy']['object'] = platform['id']


def observation_build(data, field):
    """Builds an observation."""
    with open("json/observation.json") as jFile:
        observation = json.load(jFile)
        observation['id'] = observation['id'] + data[IDENTIFIER] + ":" + field
        observation['sosa:hasSimpleResult']['value'] = data[field]
        ts = dateutil.parser.parse(data['published_at']).astimezone(dateutil.tz.tzutc())
        observation['sosa:hasSimpleResult']['observedAt'] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        observation['sosa:resultTime']['value'] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        return observation


def observation_addstream(observation, stream):
    """Adds a stream to an observation."""
    observation['iot-stream:belongsTo']['object'] = stream['id']


def observation_addsensor(observation, sensor):
    """Adds a sensor to an observation."""
    observation['sosa:madeBySensor']['object'] = sensor['id']


def observation_addobservableproperty(observation, observableproperty):
    """Adds an observable property to an observation."""
    observation['sosa:observedProperty']['object'] = observableproperty['id']


def create_ngsi_entity(ngsi_msg):
    """Threaded version for __create_ngsi_entity to avoid blocking."""
    t = threading.Thread(target=_create_ngsi_entity, args=(ngsi_msg,))
    t.start()


def _create_ngsi_entity(ngsi_msg):
    """Takes an ngsi-ld formatted entity and sends it to the broker. If already existing calls patch_ngsi_entity for
    an entity update. """
    if PRINT_NGSI:
        print("create ngsi-ld entity:")
        print(json.dumps(ngsi_msg, indent=4, sort_keys=True))
    for broker in BROKERS:
        try:
            url = "http://" + broker + "/ngsi-ld/v1/entities/"
            r = requests.post(url, json=ngsi_msg, headers=headers)
            if r.status_code == 201:
                print("Successful creation of " + ngsi_msg['id'])
            elif r.status_code == 400:
                print("Bad Request creating entity ", ngsi_msg['id'], r.text)
            elif r.status_code == 409:
                print("Already Exists (", ngsi_msg['id'], "), patch it")
                patch_ngsi_entity(ngsi_msg, broker)
            elif r.status_code == 500:
                print("Error while creating ngsi entity", r.text)
                print("Broker", broker, "Entity", ngsi_msg)
            else:
                print("Answer:", r.text)
        except requests.exceptions.ConnectionError:
            print("server not reachable?")


def patch_ngsi_entity(ngsi_msg, broker):
    """Takes an ngsi-ld formatted entity and sends it to the broker for an update."""
    # for updating entity we have to delete id and type, first do copy if needed somewhere else
    ngsi_msg_patch = dict(ngsi_msg)
    ngsi_msg_patch.pop('id')
    ngsi_msg_patch.pop('type')
    url = "http://" + broker + "/ngsi-ld/v1/entities/" + ngsi_msg['id'] + "/attrs/"
    r = requests.patch(url, json=ngsi_msg_patch, headers=headers)
    print("Patch response:", r.text, "code", r.status_code)
    if r.status_code == 204:
        print("Successful patch " + ngsi_msg['id'])


def send_local(ngsi_msg):
    """Takes an ngsi-ld formatted entity and sends it to a callback interface."""
    try:
        r = requests.post(LOCAL_URL, json=ngsi_msg, headers=headers)
        print(r.text)
    except requests.ConnectionError:
        print("Connection could not be established", LOCAL_URL)


def get_location(sensorid):
    """Helper function to get coordinates for city probe datasets."""
    locations = pandas.read_csv('data/device-locations.csv', sep=';')
    locations.set_index("deviceid", drop=False, inplace=True)
    location = locations.loc[sensorid]
    return location['latitude'], location['longitude']


if __name__ == '__main__':

    # example data from: 'https://admin.opendata.dk/api/3/action/datastore_search?offset=792392&resource_id=7e85ea85
    # -3bde-4dbf-944b-0360c6c47e3b&limit=1'

    # opens file with one example data set, could be extended to have a full working script for Aarhus city probe data
    with open('data/cityprobe_example.json') as jFile:
        example = json.load(jFile)
        records = example['result']['records']
        for record in records:
            location = get_location(record['deviceid'])
            send_message(location, record)

#!/bin/bash

docker_compose_config="-f docker-compose.yml -f docker-compose-tests.yml"

docker-compose $docker_compose_config up -d
docker-compose $docker_compose_config exec app pylint phoenix
docker-compose $docker_compose_config exec app pytest
docker-compose $docker_compose_config down

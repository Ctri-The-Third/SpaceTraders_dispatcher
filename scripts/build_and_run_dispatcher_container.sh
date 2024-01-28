docker build -f dispatcher.dockerfile -t straders_dispatcher .
docker stop straders_dispatcher
docker rm straders_dispatcher
docker run --name straders_dispatcher_instance -e POSTGRES_PASSWORD=mysecretpassword   -d straders_dispatcher 
docker build -f dispatcher.dockerfile -t straders_dispatcher .
docker stop straders_dispatcher_instance
docker rm straders_dispatcher_instance
docker run --name straders_dispatcher_instance -e POSTGRES_PASSWORD=mysecretpassword  -d straders_dispatcher
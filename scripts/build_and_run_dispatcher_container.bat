docker build -f dispatcher.dockerfile -t straders_dispatcher .
docker stop straders_dispatcher_instance
docker rm straders_dispatcher_instance
docker run --name straders_dispatcher_instance -e ST_TOKEN = 'yourtokenhere' -e ST_DB_HOST=localhost -e ST_DB_PASS=mysecretpassword -e ST_DB_PORT=6432  -d straders_dispatcher yournamehere
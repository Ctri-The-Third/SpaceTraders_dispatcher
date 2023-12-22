FROM python:latest
copy ./requirements.txt ./requirements.txt
run python -m pip install -r requirements.txt
run python -m pip install -r spacetraders_sdk/requirements.txt

Copy ./spacetraders_sdk/ ./spacetraders_sdk 
workdir spacetraders_sdk
run chmod +x ./setup.sh
run /spacetraders_sdk/setup.sh

workdir ..

copy . . 

CMD python dispatcherWK16.py 
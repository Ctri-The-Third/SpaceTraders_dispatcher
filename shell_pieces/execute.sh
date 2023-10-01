https://www.youtube.com/shorts/x3TifGqm-sI#!/bin/bash

# Run the Python file in the background
python your_script.py &

# Store the process ID (PID) of the Python script
pid=$!

# Sleep for 6 hours
sleep 6h

# Send the SIGINT signal to the Python script
kill -INT $pid

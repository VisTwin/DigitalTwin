#!/bin/bash

# Enable SSH service
sudo systemctl enable ssh
sudo systemctl start ssh

# Check SSH status
sudo systemctl status ssh

# Display the IP address
echo "Your Jetson Nano IP address is:"
hostname -I

#!/bin/bash
cd ~/projects/trustcapture/backend
python3 -m pytest tests/test_api/test_auth.py -v --tb=short

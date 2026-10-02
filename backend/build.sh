#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "===> Upgrading pip..."
python -m pip install --upgrade pip

echo "===> Installing production dependencies..."
pip install -r requirements.txt

echo "===> Collecting static files with WhiteNoise..."
python manage.py collectstatic --no-input

echo "===> Running database migrations..."
python manage.py migrate

echo "===> Build completed successfully for VayuIndex!"

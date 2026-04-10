#!/usr/bin/env bash

set -uo pipefail

# Get Github PAT
GH_TOKEN=$(aws ssm get-parameter --name "/comms-pl/github/pl-mgmt/personal-access-token" --with-decryption --query "Parameter.Value" --output text) && export GH_TOKEN

# Assume AWS role for the given account
source ./scripts/bash_assume_role.sh ${ACCOUNT_ID} ./scripts

# Fetch secrets and configuration from AWS SSM Parameter Store in the target account
API_ENVIRONMENT=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/api-environment" --with-decryption --query "Parameter.Value" --output text) && export API_ENVIRONMENT
API_KEY=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/api-key" --with-decryption --query "Parameter.Value" --output text) && export API_KEY
BASE_URL=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/base-url" --with-decryption --query "Parameter.Value" --output text) && export BASE_URL
GUKN_API_KEY=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/gukn-api-key" --with-decryption --query "Parameter.Value" --output text) && export GUKN_API_KEY
NHS_APP_OTP=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/nhs-app-otp" --with-decryption --query "Parameter.Value" --output text) && export NHS_APP_OTP
NHS_APP_PASSWORD=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/nhs-app-password" --with-decryption --query "Parameter.Value" --output text) && export NHS_APP_PASSWORD
NHS_APP_USERNAME=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/nhs-app-username" --with-decryption --query "Parameter.Value" --output text) && export NHS_APP_USERNAME
PRIVATE_KEY_CONTENTS=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/private-key" --with-decryption --query "Parameter.Value" --output text) && export PRIVATE_KEY_CONTENTS
echo $PRIVATE_KEY_CONTENTS > ./private.key
export PRIVATE_KEY=./private.key
MESH_CLIENT_CONFIG_CONTENTS=$(aws ssm get-parameter --name "/comms/${ENVIRONMENT}/release-tests/mesh-client-config" --with-decryption --query "Parameter.Value" --output text) && export MESH_CLIENT_CONFIG_CONTENTS
echo $MESH_CLIENT_CONFIG_CONTENTS > ./client_config.json
export MESH_CLIENT_CONFIG=./client_config.json

# Check for presence of all required exported variables
REQUIRED_VARS=(ACCOUNT_ID ENVIRONMENT API_ENVIRONMENT API_KEY BASE_URL GUKN_API_KEY NHS_APP_OTP NHS_APP_PASSWORD NHS_APP_USERNAME MESH_CLIENT_CONFIG OUTPUT_BUCKET PRIVATE_KEY PRIVATE_KEY_CONTENTS)
missing_vars=()
for VAR in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!VAR:-}" ]; then
    missing_vars+=("$VAR")
  fi
done
if [ ${#missing_vars[@]} -ne 0 ]; then
  echo "Error: The following required variables are not set: ${missing_vars[*]}" >&2
  exit 1
else
  echo "All required environment variables are set."
fi

# Set up Python virtual environment and install dependencies
python -m venv .venv \
  && source .venv/bin/activate \
  && poetry install

# Run pytest, capturing the exit code so it can be preserved after the S3 upload
set +e
poetry run pytest --html=tests/evidence/report.html --self-contained-html --capture=tee-sys
PYTEST_EXIT_CODE=$?
set -e

# Unset AWS credentials to drop back to default profile
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

# Upload test evidence to S3 with environment/timestamp prefix
# This always runs regardless of test outcome so the report is always available
TIMESTAMP=$(date +%Y%m%d%H%M%S)
S3_PREFIX="release-tests/${ENVIRONMENT}/${TIMESTAMP}/"

if [ -d "tests/evidence" ]; then
  echo "Uploading evidence to s3://${OUTPUT_BUCKET}/${S3_PREFIX}"
  aws s3 cp tests/evidence/ "s3://${OUTPUT_BUCKET}/${S3_PREFIX}" --recursive
else
  echo "No evidence directory found to upload."
fi

# Exit with pytest's code so the container exit code reflects the test result
exit $PYTEST_EXIT_CODE

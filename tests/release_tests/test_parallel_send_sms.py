import uuid
from helpers.constants import NHS_NUMBER_NHSAPP, PARALLEL_SEND_ROUTING_CONFIGURATION
from helpers.api.apim_request import APIHelper
from helpers.aws.aws_client import AWSClient
from helpers.test_data.user_data import UserData
from helpers.ui import nhs_app_journey
from helpers.api.govuk_notify import verify_sms_content

def test_parallel_send(api_client):
    api_helper = APIHelper(api_client)
    aws_client = AWSClient()
    
    user = [
        UserData(
            routing_plan_id=PARALLEL_SEND_ROUTING_CONFIGURATION,
            nhs_number = NHS_NUMBER_NHSAPP,
            # communication_type and supplier are used in enrich test data for GUKN requests
            communication_type = "SMS",
            supplier = "GOVUK_NOTIFY",
            message_reference= str(uuid.uuid1()),
            personalisation = "Parallel Send"
        )
    ]
    
    body = api_helper.construct_single_message_body(user[0])
    api_helper.send_and_verify_single_message_request(body, user[0])
    
    nhs_app_journey.nhs_app_login_and_view_message(personalisation=user[0].personalisation)
    
    UserData.enrich_test_data(aws_client, user)

    verify_sms_content(user[0])
    
    api_helper.poll_for_message_status(user[0].request_item, "delivered")
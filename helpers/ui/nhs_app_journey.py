from pathlib import Path
from time import sleep
from install_playwright import install
from playwright.sync_api import expect, sync_playwright
import re
import os
from helpers.logger import get_logger
from helpers.constants import PATH_TO_EVIDENCE, get_env

def nhs_app_login_and_view_message(ods_name=None, personalisation=None):
    logger = get_logger(__name__)
    debug_dir = Path(PATH_TO_EVIDENCE) / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    if ods_name is None: 
        if get_env() == "int":
           ods_name = "NHS REFERRALS"
        else:
            ods_name = "NHS ENGLAND - X26"

    with sync_playwright() as playwright:
        install(playwright.chromium)
        browser = playwright.chromium.launch(args=["--disable-features=WebAuthentication,WebAuthn"])
        page = browser.new_page()
        page.set_default_timeout(30000)
        expect.set_options(timeout=30000)

        page.goto("https://www-onboardingaos.nhsapp.service.nhs.uk/login")
        logger.info("Accessed NHS App Onboarding AOS")

        logger.info("Navigator WebAuthn available: %s", page.evaluate("() => !!window.PublicKeyCredential"))
      
        expect(page.get_by_role("heading", name="Use NHS App services", exact=True)).to_be_visible()
        page.get_by_role("button", name="Continue").click()
        logger.info(f"Continuing on to username page - {page.url}")

        expect(page.get_by_role("heading", name="Log in ")).to_be_visible()

        page.get_by_role("textbox", name="Email address", exact=True).fill(os.environ['NHS_APP_USERNAME'])
        
        page.get_by_role("textbox", name="Password", exact=True).fill(os.environ['NHS_APP_PASSWORD'])
        password = page.locator("#password-input")
        expect(password).to_have_value(os.environ["NHS_APP_PASSWORD"])
        
        page.screenshot(path=str(debug_dir / "password.png"), full_page=True)
        logger.info(f"Entered username and password - {page.url}")
        
        continue_btn = page.locator("#continue-button button")
        continue_btn.wait_for(state="visible")
        continue_btn.click()
        
        logger.info(f"Submitted login form - {page.url}")
        page.screenshot(path=str(debug_dir / "login_after_password.png"), full_page=True)
       
        page.get_by_text("Enter the security code", exact=True)
    
        page.screenshot(path=str(debug_dir / "enter_security_code.png"), full_page=True)
        logger.info(f"Current URL after OTP page check: {page.url}")
        
        if(page.url.endswith("/passkey-user-login-failed")):
            logger.warning("Login failed, likely due to WebAuthn issue. Please check the debug screenshots for details.")
            page.goto("https://access.aos.signin.nhs.uk/enter-mobile-code")
        
        page.get_by_text("Enter the security code", exact=True)
        
        page.get_by_label("Security code", exact=True).fill(os.environ['NHS_APP_OTP'])
        page.get_by_role("button", name="Continue").click()
        logger.info("Entered OTP")

        page.locator(".loading-spinner").wait_for(state="hidden")
        page.wait_for_url('**/patient/**')
        
        if(page.url.endswith("/patient/whats-new")):
            page.get_by_role("button", name="Continue").click()
            
      #  expect(page.get_by_text('NHS number: 973 680 5395')).to_be_visible()
      #  logger.info("Login journey success!")
      
        page.get_by_role("link", name="Messages").click()

        link_text = re.compile(r"You have \d+ unread messages")
        #page.get_by_role("link", name=link_text).click()
        logger.info("Navigated to message hub")

        expect(page.get_by_role("heading", name="Messages")).to_be_visible()
        page.get_by_role("link", name="Your NHS healthcare services", exact=False).first.click()
        logger.info("Navigated to messages")

        expect(page.get_by_role("heading", name="Your messages")).to_be_visible()
        page.get_by_role("link", name="Unread message from", exact=False).first.click()
        logger.info("Selected unread messages")

        page.wait_for_url("**/patient/messages/app-messaging/app-message?messageId=**")
        expect(page.get_by_role("heading", name=ods_name)).to_be_visible()
        expect(page.get_by_text(f"NHS Notify Release: {personalisation}")).to_be_visible()
        evidence_path = f"{PATH_TO_EVIDENCE}/{personalisation.replace(' ', '_')}/nhsapp.png"
        page.screenshot(path=evidence_path)
        logger.info("NHS App message appears as expected")

        page.get_by_role("link", name="Home", exact=True).click()
        page.get_by_role("link", name="Log out").click()
        
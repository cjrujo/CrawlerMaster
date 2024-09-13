import streamlit as st
import validators
import time
import os
from dotenv import load_dotenv

import base64  # Import base64 for decoding the screenshot data

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import google.generativeai as genai

# Load environment variables
load_dotenv()
#GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_API_KEY = st.secrets.get("GOOGLE_API_KEY")

# Configure the Gemini AI client
genai.configure(api_key=GEMINI_API_KEY)

# Set up the Streamlit app
st.title('Webpage Analyzer with Gemini AI')
st.write('Enter a URL to analyze the webpage content using Gemini AI.')

# Initialize session state for chat history and other variables
if 'chat_session' not in st.session_state:
    st.session_state.chat_session = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'file' not in st.session_state:
    st.session_state.file = None
if 'model' not in st.session_state:
    st.session_state.model = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'reset' not in st.session_state:
    st.session_state.reset = False
if 'user_input' not in st.session_state:
    st.session_state.user_input = ''

# Reset the app when the reset button is clicked
def reset_app():
    st.session_state.chat_session = None
    st.session_state.messages = []
    st.session_state.file = None
    st.session_state.model = None
    st.session_state.analysis_done = False
    st.session_state.reset = True
    st.session_state.user_input = ''
    st.rerun()

# Add a reset button at the top
if st.button('Reset App'):
    reset_app()

# URL input
url = st.text_input('Enter the URL of the webpage you want to analyze:', value='', key='url_input')

if url and not st.session_state.analysis_done:
    if validators.url(url):
        st.success('Valid URL')

        # Display preview of the URL content
        st.subheader('Webpage Preview')
        try:
            st.components.v1.iframe(url, height=600, scrolling=True)
        except Exception as e:
            st.error('Unable to display a preview of the webpage.')
            st.error(f'Error: {e}')

        # Automatically capture the webpage as an image
        with st.spinner('Capturing webpage...'):
            output_path = 'webpage_screenshot.png'
            try:
                def capture_fullpage_screenshot(url, output_path):
                    options = Options()
                    options.add_argument('--headless')
                    options.add_argument('--disable-gpu')
                    options.add_argument('--ignore-certificate-errors')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--no-sandbox')
                    options.add_argument('--hide-scrollbars')
                    options.add_argument('--force-device-scale-factor=1')

                    # Create a Service object
                    service = Service(ChromeDriverManager().install())

                    # Initialize the Chrome driver with the Service object and options
                    driver = webdriver.Chrome(service=service, options=options)
                    driver.get(url)
                    # Wait for the page to load
                    time.sleep(2)

                    # Get the total width and height of the page
                    total_width = driver.execute_script("return Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth);")
                    total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")

                    # Set the window size to the total page size
                    driver.set_window_size(total_width, total_height)
                    time.sleep(2)

                    # Capture the screenshot using Chrome DevTools Protocol
                    screenshot = driver.execute_cdp_cmd('Page.captureScreenshot', {'captureBeyondViewport': True})
                    screenshot_data = screenshot.get('data', '')

                    # Decode and write the image
                    with open(output_path, 'wb') as f:
                        f.write(base64.b64decode(screenshot_data))

                    driver.quit()

                capture_fullpage_screenshot(url, output_path)
                st.success('Webpage captured successfully!')
                st.image(output_path)

                # Initialize the model and chat session
                def initialize_chat():
                    try:
                        # Set temperature to default value 0.1
                        temperature = 0.1

                        # Create the model with default temperature
                        generation_config = {
                            "temperature": temperature,
                        }

                        # Updated system instruction with Chain-of-Thought
                        system_instruction = """
You are an AI assistant that analyzes webpage content. For each webpage, you should:

1. Carefully read and understand the content step by step.
2. Identify and extract the most important information related to the main topic.
3. Exclude any information not related to the topic.
4. Provide both a concise summary and the full content.
5. Present both the summary and the full content in English and Chinese (bilingual).
6. Use clear and accurate language in both languages.

Please note that the webpage is a screenshot of a webpage, not the actual webpage.
Please must use chain-of-thought reasoning and think step by step during your analysis implicitly.
"""

                        st.session_state.model = genai.GenerativeModel(
                            model_name="gemini-1.5-flash-exp-0827",
                            generation_config=generation_config,
                            system_instruction=system_instruction,
                        )

                        # Upload the image
                        st.session_state.file = genai.upload_file(output_path, mime_type="image/png")

                        # Start chat session
                        st.session_state.chat_session = st.session_state.model.start_chat(
                            history=[
                                {
                                    "role": "user",
                                    "parts": [
                                        st.session_state.file,
                                    ],
                                },
                            ]
                        )

                        # Initial analysis
                        initial_response = st.session_state.chat_session.send_message(
                            "Please analyze the content of this webpage as per the instructions."
                        )

                        # Store initial messages
                        st.session_state.messages.append(("Assistant", initial_response.text))
                        st.session_state.analysis_done = True
                        st.rerun()
                    except Exception as e:
                        st.error(f'An error occurred during analysis: {e}')

                # Initialize chat if not already done
                if st.session_state.chat_session is None:
                    initialize_chat()
            except Exception as e:
                st.error(f'An error occurred while capturing the webpage: {e}')
    else:
        st.error('Invalid URL. Please enter a valid URL.')

# After analysis is done, display chat interface
if st.session_state.analysis_done:
    st.subheader('Chat with Gemini AI')

    # Display chat history
    for sender, message in st.session_state.messages:
        if sender == 'User':
            st.markdown(f"**You:** {message}")
        else:
            st.markdown(f"**Gemini AI:** {message}")

    # Function to send message
    def send_message():
        user_input = st.session_state['user_input']
        if user_input.strip() != "":
            # Display user's message
            st.session_state.messages.append(("User", user_input))
            # Send message to Gemini AI
            with st.spinner('Gemini AI is typing...'):
                try:
                    response = st.session_state.chat_session.send_message(user_input)
                    # Display assistant's response
                    st.session_state.messages.append(("Assistant", response.text))
                except Exception as e:
                    st.error(f'An error occurred during the chat: {e}')
            # Clear the input box
            st.session_state['user_input'] = ''
            # Rerun the app to update the chat display
            st.rerun()
        else:
            st.warning('Please enter a message to send.')

    # User input for chat
    user_input = st.text_input("Ask a follow-up question:", key="user_input", on_change=send_message)

    # Prepare conversation for download
    conversation = ""
    for sender, message in st.session_state.messages:
        conversation += f"{sender}: {message}\n\n"

    # Download conversation button
    st.download_button(
        label='Download Conversation',
        data=conversation,
        file_name='conversation.txt',
        mime='text/plain',
        key="download_button"
    )

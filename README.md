# Webex UI GenAIOps Demonstration App

## Overview

**Webex UI GenAIOps** serves as a conceptual demonstration of the production-level CX GenAIOps system. When deployed in an **AI Full-Stack Lab** environment for demonstration purposes, it is primarily used to:

- Collect insights from tools across all layers of the AI full stack.
- Correlate data from various layers based on specific task requirements.
- Use prompt engineering to deliver correlated data to OpenAI’s API for intelligent responses.

This process can also dynamically employ **Retrieval-Augmented Generation (RAG)** to query local knowledge bases. The RAG approach ensures responses are more precise and exhibit lower levels of hallucination, tailored to specific tasks.

For detailed demonstration procedures, refer to the **AI Full Stack Demo Playbook**.

- **Webex UI GenAIOps** is a lightweight demonstration version of the CX GenAIOps system. Unlike the CX version, it does not include:
  - A dedicated CX web interface,
  - A localized CX fine-tuned large model,
  - An AI-Syslog data processing engine.

  Instead, it features:
  - **Webex ChatBot** as the user interface,
  - **OpenAI** as the AI engine,
  - Integration with more Cisco full-stack systems, such as Kubernetes, ACI, NDI, ThousandEyes, Hubble, and Tetragon.

- Outside the Cisco PM Lab environment, the demonstration version adapts to local environments that may lack external systems like ACI, NDI, and ThousandEyes. The tightly coupled integration with these systems is removed, and the results are loaded as module variables via `credentials.py`.

- To simplify installation and code modification for the demo environment:
  - The entire setup is packaged as an **all-in-one container image** (~650MB), including all functionality and dependencies.
  - No additional images are required for deployment.
  - Follow the installation steps provided separately to set up an environment suitable for running the container.

## Application Components

 This code was modified based on ThousandEyes Webex Bot of Cisco Devnet Learning Lab and David Tian's work. I added new functions, new AI Agent codes, and interactions with Cisco's full-stack observability tools and network controllers.

1. **`gptwebexbot.py`**:
   - The container image includes the complete main application file `gptwebexbot.py`.
   - Modify it in the local environment to meet specific demo requirements.
   - Note: The file contains "unused code" from previous demo modifications. You may remove irrelevant sections after confirming they are not needed for the local setup to optimize efficiency.

2. **`credentials.py`**:
   - This file contains credentials (e.g., Webex Token, OpenAI API Key, and external system API Keys) required for the application.
   - It is loaded as a Kubernetes Secret during runtime.
   - After installation, delete this file to ensure security and confidentiality. This file is not suitable for public and can only be provided separately.

3. **`test_kb.md`**:
   - This is a test RAG (Retrieval-Augmented Generation) external knowledge base.
   - It provides professional knowledge required during the demo. For examples, during security-related demos, privileges can be escalated to modify this knowledge base to simulate attacks.
   - The file is placed in a specific directory on the node running the `gptwebexbot` container and is called during container startup. This file is not suitable for public and can only be provided separately.

## Webex UI GenAIOps Workflow

The Webex UI GenAIOps operates as a typical **Webhook-based chatbot**. The working mechanism is as follows:

### 1. Registering the Webhook
- **Target System**: Create a listening URL endpoint in the target system (e.g., your application’s web server) known as the **Webhook URL**.
- **Source System**: Register this URL in the source system (e.g., Webex Bot) as a **Webhook registration**.

### 2. Event Triggering
- When a specific event occurs in the source system (e.g., receiving a user’s chat query), the event triggers the Webhook.

### 3. Sending Notifications
- Once triggered, the source system (e.g., Webex Bot) sends an HTTP request (typically a POST request) to the registered Webhook URL.
- The request contains event-related data (e.g., the user’s chat query).

### 4. Receiving and Processing
- The target system’s Webhook URL (e.g., your web server or `ngrok`) receives the request.
- It parses the data and processes it (e.g., integrating and generating prompts, requesting answers from OpenAI, and formatting the OpenAI response as a chat reply).

### 5. Returning Results
- The target system (e.g., your application’s web server) sends the processed response (e.g., a chat reply) back to the source system (e.g., Webex Bot).
- The source system handles the response (e.g., displaying the chat reply to the user).

### Advantages of Webhook Mechanism
- Enables the target system (web server) to respond in real-time to events in the source system (Webex Bot).
- Eliminates the need for constant querying or polling of the source system for updates.

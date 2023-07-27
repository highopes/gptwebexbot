from webexteamsbot import TeamsBot
from gpt_webex.credentials import *
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.document_loaders import TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
import os
import requests
import logging
import json
import re
import openai
import paramiko

requests.packages.urllib3.disable_warnings()

openai.api_key = OPENAI_KEY

# following is the function for OpenAI to select
FUNCTIONS = [
    {
        "name": "k8s_status",
        "description": "Explicitly ask for the status of Kubernetes and the resource component, or request that a new resource be created",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string",
                             "description": "the language of the question"},
                "kubernetes": {"type": "string",
                               "description": "the name of the Kubernetes cluster or context, if not mentioned, set value to empty string"},
                "namespace": {"type": "string",
                              "description": "the name of the namespace, if not mentioned, set value to empty string"},
                "service": {"type": "string",
                            "description": "the name of the specific microservice or service, if not mentioned, set value to empty string"}
            },
            "required": ["language", "kubernetes", "namespace", "service"]
        }
    },
    {
        "name": "k8s_fso",
        "description": "Request an explanation of why the service or microservice's user experience has deteriorated.",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string",
                             "description": "the language of the question"},
                "kubernetes": {"type": "string",
                               "description": "the name of the Kubernetes cluster or context, if not mentioned, set value to empty string"},
                "namespace": {"type": "string",
                              "description": "the name of the namespace, if not mentioned, set value to empty string"},
                "service": {"type": "string",
                            "description": "the name of the specific microservice or service, if not mentioned, set value to empty string"}
            },
            "required": ["language", "kubernetes", "namespace", "service"]
        }
    },
    {
        "name": "personal_cv",
        "description": "Handle when a question is asked about a character that cannot be answered by the AI model's existing knowledge.",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string",
                             "description": "the language of the question"},
                "name": {"type": "string",
                         "description": "the name of the person asked about"}
            },
            "required": ["language", "name"]
        },
    },
    {
        "name": "aci_knowledge",
        "description": "Handle technical knowledge related to Cisco ACI (Application Centric Infrastructure).",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string",
                             "description": "the language of the question"},
                "type": {"type": "string",
                         "description": "Types of Cisco ACI technologies asked about, e.g. scalability"}
            },
            "required": ["language", "type"]
        },
    }
]

# Following is the extra prompt when call OpenAI API
PROMPT_k8s_fso = ('''\nThe following is the information I obtained from the underlying network,  '''
                  '''please answer the question based on this information: \n  ''')

PROMPT_k8s_status = ('''You are now an application and I give you an administrative task below about the  '''
                     '''Kubernetes system,  you give the command line to complete that task directly.  '''
                     '''Note that this Kubernetes cluster is version 1.21, installed using kubeadm,  '''
                     '''the CNI is Calico, the IPIP tunnel setting is Never, and the SNAT feature is turned off.  '''
                     '''Use the command that best fits this cluster environment.  '''
                     '''Your answer must only contain ONE command line in plain text  '''
                     '''that I can execute directly without any modification.  '''
                     '''The commands you can use, but are not limited to:  '''
                     '''kubectl, kubeadm, calicoctl, kubelet, kubernetes-cni, etcdctl, helm, kubefed,  '''
                     '''kubectl-debug, kubectl-trace, ...etc.  '''
                     '''Do not use any formatting notation, just give the command line itself!  '''
                     '''I give the following task:  ''')

PROMPT_k8s_status_prefix = ('''\nThe following is the information I obtained from the target system,  '''
                            '''please answer the question based on this information: \n  ''')

base_url = "https://api.thousandeyes.com/v6/"

# chatGPT url and Header
# chatGPT_url = "https://api.openai.com/v1/completions"
# url = "https://api.openai.com/v1/engines/text-davinci-003/jobs"
chatGPT_headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + openai.api_key
}

bot = TeamsBot(
    TEAMS_BOT_APP_NAME,
    teams_bot_token=WEBEX_TEAMS_ACCESS_TOKEN,
    teams_bot_url=TEAMS_BOT_URL,
    teams_bot_email=TEAMS_BOT_EMAIL,
    debug=True,
    webhook_resource_event=[
        {"resource": "messages", "event": "created"},
    ],
)

TE_headers = {
    "Authorization": "Bearer " + TETOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json"
}

try:
    """
    added by Weihang: create Q&A Object qa to answer question with knowledge bases
    """
    current_path = os.path.dirname(os.path.abspath(__file__))
    os.environ['OPENAI_API_KEY'] = OPENAI_KEY
    llm = ChatOpenAI(model=MODEL_LANGCHAIN, temperature=0)

    loader = TextLoader(os.path.join(
        current_path, KNOWLEDGE_BASE), encoding="utf-8")
    documents = loader.load()[0].page_content  # Load markdown in plain text
    # split the text
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    text_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on)
    texts = text_splitter.split_text(documents)

    # Embeddings
    embeddings = OpenAIEmbeddings()

    # put into vector store Chroma and leverage its native retrieve method instead of LLM's self-querying
    docSearch = Chroma.from_documents(texts, embeddings)

    # Build retrieve mode
    retriever = docSearch.as_retriever(
        search_type="similarity_score_threshold", search_kwargs={"score_threshold": .5})

    # Build a Q&A chain with LangChain
    qa = RetrievalQA.from_chain_type(
        llm, chain_type="stuff", retriever=retriever)
    print(f"Knowledge base {KNOWLEDGE_BASE} has been successfully loaded.")
except:
    print("Knowledge base loading failed.")


def configbyssh(host, cmd):
    '''
    added by Weihang. SSHClient Testing
    '''
    try:
        # create sshClient obj
        ssh = paramiko.SSHClient()
        # trust remote host, allow access
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    except:
        print("There is an error with the SSHClient")
    try:
        # connect to remote host
        ssh.connect(host["host"],
                    host["port"],
                    host["user"],
                    host["pass"])
    except:
        print("Failed to connect to remote server")
    ''' 
    execute the commands 
    '''
    try:
        # note that every time we execute will be in new env
        stdin, stdout, stderr = ssh.exec_command(cmd)

        if stderr.readlines():
            print(stderr.readlines())

        result = stdout.read()
        result_str = result.decode('utf-8')

        return result_str

    except:
        print('Fail to execute command')

    # close ssh session
    ssh.close()


# A simple command that returns a basic string that will be sent as a reply
def list_agents(incoming_msg):
    message = "TE said:\nHere is your list of agents:<br /><br />"
    res = requests.get(url=base_url + "endpoint-agents", headers=TE_headers)
    data = json.loads(res.text)
    for agent in data['endpointAgents']:
        message = message + \
            (f"Agent Name: {agent['agentName']} - Type: {agent['agentType']}<br />")

    return message


def list_tests(incoming_msg):
    message = "TE said:\nHere is your list of tests:<br /><br />"
    res = requests.get(url=base_url + "tests", headers=TE_headers)
    data = json.loads(res.text)
    for test in data['test']:
        message = message + \
            (f"Test ID: {test['testId']} - Type: {test['type']} - Test Name: {test['testName']}<br />")

    return message


def test_details(incoming_msg):
    message = incoming_msg.text
    test_id = str(re.sub('[^0-9]', '', message))
    res = requests.get(url=base_url + "tests/" + test_id, headers=TE_headers)
    data = json.loads(res.text)
    print(data)
    for test in data['test']:
        message = f"""Test ID: {test['testId']}
                    Type: {test['type']}
                    Test Name: {test['testName']}
                    Interval: {test['interval']}
                    Path Traces: {test['numPathTraces']}"""

    return message


# Active alarm
def list_alerts(incoming_msg):
    message = "TE Said:\nHere is your list of active alert:<br /><br />"
    res = requests.get(url=base_url + "alerts", headers=TE_headers)
    data = json.loads(res.text)
    print(data)
    for test in data['alert']:
        message = message + (f"Type: {test['active']} <br />")

    return message


# chatGPT
def chat_withoutlog(prompt, model=MODEL_SPC):
    """
    add by Weihang
    """
    messages = [{"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}]

    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        n=1,
        stop=None,
        temperature=0.5,
    )

    return response.choices[0].message['content']


def chatGPT_send_message(message_log):
    # Use OpenAI's ChatCompletion API to get the chatbot's response
    response = openai.ChatCompletion.create(
        model=MODEL_GEN,  # The name of the OpenAI chatbot model to use
        # model="gpt-4",  # The name of the OpenAI chatbot model to use
        # The conversation history up to this point, as a list of dictionaries
        messages=message_log,
        # The maximum number of tokens (words or subwords) in the generated response
        max_tokens=3800,
        # The stopping sequence for the generated response, if any (not used here)
        stop=None,
        # The "creativity" of the generated response (higher temperature = more creative)
        temperature=0.7,
    )

    # Find the first response from the chatbot that has text in it (some responses may not have text)
    for choice in response.choices:
        if "text" in choice:
            return choice.text

    # If no response with text is found, return the first response's content (which may be empty)
    return response.choices[0].message.content


def chatGPT_main(questions):
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    user_input = questions
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append(
        {"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response2 = response
    return response2


def ask_ChatGPT(questions):
    ask_questions = questions.text
    message = chatGPT_main(ask_questions)

    return message


# vManage Alarm
# vManage API endpoint for fetching alarms
def vManage_alarms(incoming_msg):
    message = "SDWAN Said:\nSDWAN Vmanage is under instruction,will update soon <br /><br />"

    return message


# SecureX API endpoint for fetching alarms
def securex_alarms(incoming_msg):
    message = "SecureX Said:\n SecureX Incident getting is under instruction, will update soon <br /><br />"

    return message


def for_help(incoming_msg):
    message = "Please contact xueatian@cisco.com for further discussion. Do not contact hangwe@cisco.com :)"

    return message


def get_token():
    auth_url = f"https://{dnac_ip}/dna/system/api/v1/auth/token"
    token = requests.post(
        auth_url, auth=(username, password),
        headers={"content-type": "application/json"},
        verify=False, )

    data = token.json()
    print(data)
    return data["Token"]


def get_issue_list_from_dnac(incoming_msg):
    message = "DNAC on Devnet Sanbox Said:\nHere is your list of active Issues:<br /><br />"
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}
    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        print(str(a) + ':' + items_name)
        message = message + (str(a) + "  :"f"Issue Name: {items_name} <br />")
        a += 1
    print(message)
    return message


# Ask the reason for Issue on ChatGPT
def ask_reason(number):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number)
    print(type(number))
    match = re.search(r'/ask-reason\s+(\S+)', number)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    main_questions = "what is the meaning and main reason for"
    main_questions2 = "do not need the guide to fix it "
    user_input = main_questions + questions + main_questions2
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append(
        {"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response2 = "AI said:\n" + response
    return response2


def ask_guide(number2):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number2)
    print(type(number2))
    match = re.search(r'/ask-guide\s+(\S+)', number2)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    # main_questions = "please guide me how to fix this issue\" "
    main_questions = "请指导我如何处理这个告警\" "
    main_questions2 = "\"including the command line on device , and summary all the command line together finally "
    user_input = main_questions + questions + main_questions2
    print(user_input)
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append(
        {"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response3 = "AI said:\n" + response
    return response3


def ask_guide_chinese(number2):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number2)
    print(type(number2))
    match = re.search(r'/ask-chinese-guide\s+(\S+)', number2)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    main_questions = "please guide me how to fix this issue\" "
    main_questions2 = "\" including the command line on device ,summary all the command line together finally,and describe that in Chinese only "
    user_input = main_questions + questions + main_questions2
    print(user_input)
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append(
        {"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response3 = "AI said:\n" + response
    return response3


def ask_ChatGPT_reason(questions_number):
    ask_number = questions_number.text
    message = ask_reason(ask_number)

    return message


def ask_ChatGPT_guide(questions_number):
    ask_number = questions_number.text
    message = ask_guide(ask_number)

    return message


def ask_ChatGPT_guide_chinese(questions_number):
    ask_number = questions_number.text
    message = ask_guide_chinese(ask_number)

    return message


def get_flow_anomalies(ip):
    """
    added by Weihang
    """
    # ToDo:  use NDI API to get anomalies related to ip addresses, and return anomalies list

    return anomaly


def get_svc_address(svc):
    """
    added by Weihang
    """
    # ToDo:  use kubectl get pods -A -l app=svc -o jsonpath='{range .items[*]}{.status.podIP}{","}{end}' to get ip addesses

    return ip


def check_svc_network(svc):
    """
    added by Weihang
    """
    ipadd = []
    ipadd.extend(get_svc_address(svc))
    str = ""
    if ipadd:
        str = get_flow_anomalies(ipadd)

    return str


def extract_cmdline(multiline_string):
    """
    added by Weihang
    """
    # cut the multiline string into a list
    lines = multiline_string.split('\n')

    # regex match rules, limit to some popular commands
    regex = re.compile(
        '(kubectl|kubeadm|calicoctl|kubelet|kubernetes-cni|etcdctl|helm|kubefed|kubectl-debug|kubectl-trace|systemctl)')

    # Iterate through each line and return the entire line if it matches
    for line in lines:
        if regex.search(line):
            return line


def k8s_status(args, text):
    """
    added by Weihang
    """
    if args.get("namespace") and args.get("namespace") != 'default':
        question = PROMPT_k8s_status + \
            "In the namespace {}, ".format(args["namespace"]) + text
    else:
        question = PROMPT_k8s_status + text
    print("question ---> ", question)
    k8s_cmd = extract_cmdline(chat_withoutlog(question))
    print(k8s_cmd)
    cmd_response = configbyssh(SSH_HOST, k8s_cmd)
    if cmd_response:
        answer = cmd_response
    else:
        answer = "information not found"

    print("answer --->", answer)
    return PROMPT_k8s_status_prefix + answer


def k8s_fso(args):
    """
    added by Weihang
    """
    anomalies = ""
    if args.get("service"):
        anomalies = check_svc_network(args["service"])

    print("anomalies ---> ", anomalies)
    if anomalies:
        answer = anomalies
    else:
        answer = "information not found"

    print("answer --->", answer)
    return PROMPT_k8s_fso + answer


def openai_call_function(messages):
    """
    added by Weihang
    """
    response = openai.ChatCompletion.create(
        model=MODEL_SPC,
        messages=messages,
        functions=FUNCTIONS
    )

    return response


def ask_kb(msg):
    """
    added by Weihang: demostrate function calling without vector embedding
    """
    answer = ""
    msg_txt = msg.text
    if msg_txt.startswith("/ask"):
        msg_txt = msg_txt[len("/ask"):]  # remove "/ask"

    # Function calling analytics
    response = openai_call_function([{"role": "user", "content": msg_txt}])

    # if find the proper function, then...
    if response['choices'][0]['message'].get("function_call"):
        # Output function name and arguments
        function_name = response['choices'][0]['message']['function_call']['name']
        args = json.loads(response['choices'][0]
                          ['message']['function_call']['arguments'])
        print("Function Name: ", function_name)
        print("Arguments: ", args)

        # Call the corresponding function and get the result
        if function_name == "k8s_status":
            result = k8s_status(args, msg_txt)
        elif function_name == "k8s_fso":
            result = k8s_fso(args)
        elif function_name == "personal_cv":
            answer = qa.run(
                msg_txt + "(Please answer in the language of the question)")
        elif function_name == "aci_knowledge":
            answer = qa.run(
                msg_txt + "(Please answer in the language of the question)")

        # if not answered, send the result back to the OpenAI model to generate the final answer
        if not answer:
            response = openai_call_function([
                {"role": "user", "content": msg_txt},
                {"role": "assistant", "content": None,
                 "function_call": {"name": function_name, "arguments": json.dumps(args)}},
                {"role": "function", "name": function_name, "content": result},
            ])
            answer = response['choices'][0]['message']['content']

    else:
        # if we didn't find the proper function, response normally
        answer = response['choices'][0]['message']['content']

    print("Final Answer: ", answer)
    return answer


# Add new commands to the box.
bot.add_command("/SDWAN-listalarms",
                "This will list the active alarms from SDWAN Vmanage", vManage_alarms)
bot.add_command(
    "/gethelp", "please contact with xueatian@cisco.com. Do not contact hangwe@cisco.com :)", for_help)
bot.add_command("/te-listagents",
                "This will list the endpoint agents", list_agents)
bot.add_command("/te-listtests", "This will list the tests", list_tests)
bot.add_command("/te-testdetails",
                "This will provide more information about a test with the given Test ID (e.g. /testdetails 12345)",
                test_details)
bot.add_command("/te-listalerts",
                "This will list the active alerts", list_alerts)
bot.add_command(
    "/ai", "ask questions to chatGPT, (e.q. /ai how beautiful is the life )", ask_ChatGPT)
bot.add_command("/dnac-listissues",
                "This will list the active issues from DNAC", get_issue_list_from_dnac)
bot.add_command("/ask-reason",
                "ask the detail description on the DNAC issue with chatGPT,input the issue number (e.q. /ask-reason  1 )",
                ask_ChatGPT_reason)
bot.add_command("/ask-guide",
                "ask the guide on how to fix the issues on DNAC with chatGPT,input the issue number (e.q. /ask-guide  1 )",
                ask_ChatGPT_guide)
bot.add_command("/ask-chinese-guide",
                "让chatGPT用中文描述这个故障的处理建议,输入的格式为/ask-chinese-guide + 故障编号 (e.q. /ask-chinese-guide  1 )",
                ask_ChatGPT_guide_chinese)
bot.add_command("/secure-listincidents", "This will list the active security incidents from SecureX platform ",
                securex_alarms)
bot.add_command("/ask",
                "Ask the AI any question and the AI will answer it using the local knowledge base. (e.g. /ask 微服务movies的质量变差了, 网络出问题了吗; /ask 帮我在Kubernetes集群创建一个名为test001的命名空间; /ask Introducing Wei Hang from Cisco. ） ",
                ask_kb)

bot.remove_command("/echo")

if __name__ == "__main__":
    # Run Bot
    logging.basicConfig(level=logging.NOTSET, filename='output.log', filemode='a',
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('loggin on here ')
    logging.NOTSET
    bot.run(host="0.0.0.0", port=8182)

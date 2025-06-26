import random
from langchain.chains import ConversationalRetrievalChain, create_history_aware_retriever, create_retrieval_chain
from langchain.chains.llm import LLMChain
from langchain.chains.combine_documents.stuff import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.schema import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.document_loaders.csv_loader import CSVLoader
from langchain.text_splitter import CharacterTextSplitter

import spacy
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from google import genai
from google.genai import types


from app.models import *

class Gemini_RAG:
    """
    Gemini_RAG is a production-ready integration of Google Gemini with LangChain and ChromaDB.

    Features:
        * load_vectordb
        * text_splitter
        * csv_splitter
        * train
        * set_as_default_vectordb
        * make_conversation
        * generate_answer
    """

    embeddings = HuggingFaceEmbeddings(model_name="hkunlp/instructor-large")

    def __init__(self, persist_directory="./chroma_storage"):
        self.gemini_key = "key" 
        self.vectordb = None
        self.persist_directory = persist_directory
        self.memory_store = {}  # user_id: ConversationBufferMemory
        self.__message_template()

    @staticmethod
    def text_splitter(text):
        spliter = CharacterTextSplitter(separator="\n", chunk_size=4080, chunk_overlap=50)
        return spliter.split_text(text)

    @staticmethod
    def text_cleaner(text_data):
        nlp = spacy.load("en_core_web_sm")
        doc = nlp(text_data)
        clean_tokens = [token.text for token in doc if (token.text == "." or token.text == ":") or (not token.is_stop and not token.is_punct)]
        return " ".join(clean_tokens)

    @staticmethod
    def csv_splitter(file):
        load_csv = CSVLoader(file)
        return load_csv.load()

    def set_as_default_vectordb(self, db):
        self.vectordb = db

    def load_vectordb(self, collection_name="default"):
        vectordb = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        if self.vectordb is None:
            self.vectordb = vectordb
        return vectordb

    def train(self, data, is_document=False, metadata=None):
        if is_document:
            self.vectordb.add_documents(data)
        else:
            # clean_text = self.text_cleaner(data)
            texts = self.text_splitter(data)
            metadatas = [metadata] * len(texts) if metadata else None
            self.vectordb.add_texts(texts=texts, metadatas=metadatas)
        return self.vectordb

    def __message_template(self):
        system_template = '''
        You are Trizync Solution's virtual assistant, trained to professionally support and guide customers.

        Company Overview:
        Trizync Solution is a professional Ecommerce and IT service agency. We offer:
        - Marketing Consultancy
        - Website Development
        - Tracking & Analysis
        - Digital Marketing
        - Product Design
        - UI & UX Design
        - Business Automation
        - Digital Product Development
        
        --------
        {context}

        Your Goal:
        - Understand the customer's intent clearly.
        - Answer questions about our services, pricing, timeline, process, or technical aspects.
        - Guide them to the right service or collect lead info if needed.
        - Be clear, professional, helpful, and friendly.
        - Use Bengali if the user writes in Bengali; otherwise, continue in English.

        Respond with:
        - A helpful and relevant answer.
        - A follow-up question or suggestion if appropriate.
        - A soft CTA (Call to Action) like: “Would you like a free consultation?” or “Can I connect you with our development team?”

        If you're unsure, ask the user for clarification.

        --- Begin your response below this line ---
        Answer between 500-1000 words do not excced the limit
        '''
        user_template = "{question}"

        messages = [
            SystemMessagePromptTemplate.from_template(system_template),
            HumanMessagePromptTemplate.from_template(user_template)
        ]
        self.__qa_prompt = ChatPromptTemplate.from_messages(messages)

    def load_user_memory_from_db(self,user_id):
        """
        Load messages from DB and return a memory object
        """
        messages = []

        # Load your saved messages for the user from DB
        rows = UserMessage.objects.filter(user__psid=user_id).order_by("-received_at")  # or limit to last 10

        for row in rows[:10]:
            messages.append(HumanMessage(content=row.text))
            messages.append(AIMessage(content=row.response))

        memory = ConversationBufferMemory(memory_key="chat_history",return_messages=True)
        memory.chat_memory.messages = messages
        return memory
    
    def add_user_details_to_message_template(user_id: str) -> str:
        try:
            user = MessengerUser.objects.get(psid=user_id)
        except MessengerUser.DoesNotExist:
            return ""

        # Collect details
        name = user.name or "Unknown"
        phone = user.phone or "Not provided"
        email = user.email or "Not provided"

        websites = UserWebsite.objects.filter(user=user).values_list('url', flat=True)
        budgets = UserBudget.objects.filter(user=user).values_list('amount', flat=True)
        services = UserService.objects.filter(user=user).values_list('name', flat=True)

        # Format them nicely
        websites_str = ", ".join(websites) if websites else "Not provided"
        budgets_str = ", ".join(map(str, budgets)) if budgets else "Not provided"
        services_str = ", ".join(services) if services else "Not provided"

        user_info = f"""
            User Info:
            -----------
            Name     : {name}
            Phone    : {phone}
            Email    : {email}
            Websites : {websites_str}
            Budget   : {budgets_str}
            Services : {services_str}
        """
        return user_info.strip()



    def make_conversation(self, user_id: str, stream=False, callback_manager=None):
        memory = self.load_user_memory_from_db(user_id)

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=self.gemini_key,
            streaming=stream,
            callback_manager=callback_manager
        )

        conversation = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=self.vectordb.as_retriever(),
            memory=memory,
            chain_type="stuff",
            combine_docs_chain_kwargs={"prompt": self.__qa_prompt},
            verbose=True
        )

        return conversation


    def generate_answer(self,user_id: str, question, stream=False, callback_manager=None):
        conversation = self.make_conversation(user_id,stream=stream, callback_manager=callback_manager)
        response = conversation.invoke(
            {"question": question}
        )
        # print(response)
        return response['answer']
    
    def generate_answer_native(self, user_id: str, user_input: str):

        model = "gemini-1.5-flash"

        # Prepare conversation context
        contents = []
        history = UserMessage.objects.filter(user__psid=user_id).order_by("-received_at")
        
        for turn in history[:10]:
            print(turn.text)
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=turn.text)]))
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text=turn.response)]))
        
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))

        # print(contents)

        generate_content_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
            system_instruction=[
                types.Part.from_text(text='''
                    You are Trizync Solution's messenger chat assistant, trained to professionally support and guide customers.

                    Company Overview:
                    Trizync Solution is a professional Ecommerce and IT service agency. We offer:
                    - Marketing Consultancy
                    - Website Development
                    - Tracking & Analysis
                    - Digital Marketing
                    - Product Design
                    - UI & UX Design
                    - Business Automation
                    - Digital Product Development
                    
                    --------

                    Your Goal:
                    - Understand the customer's intent clearly.
                    - Answer questions about our services, pricing, timeline, process, or technical aspects.
                    - Guide them to the right service or collect lead info if needed.
                    - Be clear, professional, helpful, and friendly.
                    - Use Bengali if the user writes in Bengali; otherwise, continue in English.

                    Respond with:
                    - A helpful and relevant answer.
                    - A follow-up question or suggestion if appropriate.
                    - A soft CTA (Call to Action) like: “Would you like a free consultation?” or “Can I connect you with our real time agent?”

                    If you're unsure, ask the user for clarification.

                    --- Begin your response below this line ---
                    Answer between 500-1000 words do not excced the limit
                    '''
                )
            ]
        )

        client = genai.Client(api_key=self.gemini_key)

        # Generate content (non-streaming)
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config
        )

        return response.text



# rag = Gemini_RAG()
# rag.load_vectordb()

text_data = '''
Trizync Solution is a professional Ecommerce and IT service agency. We offer a range of solutions to help businesses grow and operate more efficiently. Our services include:

1. Marketing Consultancy – We guide businesses in creating data-driven marketing strategies tailored to their audience and goals.

2. Website Development – We build responsive, fast, and secure websites including eCommerce platforms, business portals, and landing pages.

3. Tracking & Analysis – We implement tools like Google Analytics, Meta Pixel, and custom dashboards to measure performance and user behavior.

4. Digital Marketing – We manage campaigns across Facebook, Google, Instagram, and other platforms for lead generation, sales, and brand awareness.

5. Product Design – We help visualize and plan digital products through wireframing, prototyping, and functional design strategies.

6. UI & UX Design – We craft intuitive, user-friendly interfaces with focus on aesthetics, usability, and conversion optimization.

7. Business Automation – We integrate tools to automate business workflows such as CRMs, emails, analytics, customer support, etc.

8. Digital Product Development – We build full-stack, scalable digital products including SaaS platforms, internal tools, and mobile/web apps.

Trizync aims to deliver scalable, reliable, and conversion-oriented solutions to businesses of all sizes.
'''
metadata = {
    "source": "Trizync_Solution_Official",
    "category": "services",
    "language": "en",
  }

# rag.train(data=text_data, is_document=False, metadata=metadata)
# rag.generate_answer('23231',"hi")
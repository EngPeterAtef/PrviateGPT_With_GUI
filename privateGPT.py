#!/usr/bin/env python3
from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.vectorstores import Chroma
from langchain.llms import GPT4All, LlamaCpp
import os
import argparse
import time
import streamlit as st
from langchain.docstore.document import Document
from ingest import main as ingest_main

load_dotenv()

embeddings_model_name = os.environ.get("EMBEDDINGS_MODEL_NAME")
persist_directory = os.environ.get('PERSIST_DIRECTORY')

model_type = os.environ.get('MODEL_TYPE')
model_path = os.environ.get('MODEL_PATH')
model_n_ctx = os.environ.get('MODEL_N_CTX')
model_n_batch = int(os.environ.get('MODEL_N_BATCH',8))
target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4))

from constants import CHROMA_SETTINGS

def main():
    # Parse the command line arguments
    args = parse_arguments()
    embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
    db = Chroma(persist_directory=persist_directory, embedding_function=embeddings, client_settings=CHROMA_SETTINGS)
    retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})
    # activate/deactivate the streaming StdOut callback for LLMs
    callbacks = [] if args.mute_stream else [StreamingStdOutCallbackHandler()]
    # Prepare the LLM
    match model_type:
        case "LlamaCpp":
            llm = LlamaCpp(model_path=model_path, n_ctx=model_n_ctx, n_batch=model_n_batch, callbacks=callbacks, verbose=False)
        case "GPT4All":
            llm = GPT4All(model=model_path, n_ctx=model_n_ctx, backend='gptj', n_batch=model_n_batch, callbacks=callbacks, verbose=False)
        case _default:
            # raise exception if model_type is not supported
            raise Exception(f"Model type {model_type} is not supported. Please choose one of the following: LlamaCpp, GPT4All")
        
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents= not args.hide_source)
    

    # configure the streamlit app
    st.set_page_config(page_title="privateGPT", page_icon="💬", layout="wide")
    st.title("Private GPT: Ask questions to your documents.")
    # header of the page
    st.header("Chat with your documents")
    # add side bar
    with st.sidebar:
        st.subheader("Your Documents")
        files = st.file_uploader('Upload your documents', type=['pdf', 'txt', 'docx', 'doc', 'pptx', 'ppt', 'csv','enex','eml','epub','html','md','odt',], accept_multiple_files=True, key="upload")
        # convert files form list of UploadedFile to list of Document
        
        if st.button("Process Documents"):
            # add a spiner
            with st.spinner("Processing your documents..."):
                # get the text in the documents
                ingest_main(files)
    # create text input
    query = st.text_input("Enter a query: ")
    if query:
        # then pass the query to the qa model
        # Get the answer from the chain
        start = time.time()
        res = qa(query)
        # res = "This is a test"
        answer, docs = res['result'], [] if args.hide_source else res['source_documents']
        end = time.time()
        # write the answer to the screen
        st.write(answer)
        # Print the time taken to answer the question
        st.write(f"\n> Answer (took {round(end - start, 2)} s.):")
        # Print the relevant sources used for the answer
        # for document in docs:
        #     st.write("\n> " + document.metadata["source"] + ":")
        #     st.write(document.page_content)
        #     st.write("\n")


def parse_arguments():
    parser = argparse.ArgumentParser(description='privateGPT: Ask questions to your documents without an internet connection, '
                                                 'using the power of LLMs.')
    parser.add_argument("--hide-source", "-S", action='store_true',
                        help='Use this flag to disable printing of source documents used for answers.')

    parser.add_argument("--mute-stream", "-M",
                        action='store_true',
                        help='Use this flag to disable the streaming StdOut callback for LLMs.')

    return parser.parse_args()


if __name__ == "__main__":
    main()
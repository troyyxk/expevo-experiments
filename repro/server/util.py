import re

def log_flush(fileIO, txt: str):
    """
    Write and flush to the disk.
    """
    fileIO.write(txt)
    fileIO.write("\n")
    fileIO.flush()


def clean_string(input_string):
    """
    Cleans the input string by removing \n and *.
    """
    return re.sub(r'[\n|*|\'|\"]', '', input_string.strip()).strip()


def cut_last_appearance(txt: str, keyword: str) -> str:
    """
    Cut the txt after the last appearance of the keyword.
    """
    result_start = txt.rfind(keyword)
    if result_start < 0:
        raise Exception("In retrieve_llama_summarized_content(), there should be a keyword but there isn't")
    result_start += len(keyword)
    result = txt[result_start:].strip()
    return result

def get_generated_text(generation_result) -> str:
    return generation_result[0]['generated_text']


def get_string_len_sum(docs: list) -> int:
    """
    Get the sum of the lengths of all strings in the list.
    """
    return sum(len(doc) for doc in docs)


def clean_str(txt: str) -> str:
    txt = txt.lower()
    cleaned = re.sub(r'[^a-z0-9 ]', '', txt)
    return cleaned


def tokenize_str(txt: str) -> list:
    clean_txt = clean_str(txt)
    return clean_txt.split()

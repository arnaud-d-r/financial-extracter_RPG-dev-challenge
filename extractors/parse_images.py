from __future__ import annotations

import datetime
import os
from pathlib import Path
import re
from unittest import result

from click import prompt
from pydantic import BaseModel
import torch
import json

from .models import  PaymentMethod, Transaction, ExtractionResult, TransactionCategory
from typing import List, Optional

os.environ["TORCHDYNAMO_DISABLE"] = "1"

import torch
import torch._dynamo

torch._dynamo.disable()
import outlines
from PIL import Image
from outlines.inputs import Image as OutlinesImage

from transformers import BitsAndBytesConfig, Qwen2VLForConditionalGeneration, AutoProcessor
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.simplefilter("ignore", FutureWarning)


model_name = "Qwen/Qwen2-VL-2B-Instruct"

tf_model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_name,
    device_map="auto",
    attn_implementation="sdpa",  # Scaled Dot-Product Attention (Fast)
    torch_dtype=torch.bfloat16,  # Crisp, non-degraded floating-point accuracy
)

tf_processor = AutoProcessor.from_pretrained(
    model_name,
    min_pixels=512*28*28,
    max_pixels=1024*28*28
)




class TransactionSimplified(BaseModel):
    category: TransactionCategory
    vendor: str
    description: str
    date: str
    amount: str
    payment_method: str

def parse_images(path: str | Path, category: TransactionCategory = TransactionCategory.RECEIPT) -> ExtractionResult:
    image_path = Path(path)


    
    with Image.open(image_path) as image:
        ONE_SHOT_PROMPT = """<|im_start|>system
        You are a precise forensic financial audit assistant specializing in data extraction from handwritten and printed receipts in English or French. Your task is to extract financial transaction data from images of receipts into a strict JSON schema.

        EXPECTED FIELD LOGIC & SEMANTICS:
        - 'category': The type of document. Must be exactly one of: "invoice", "bank_statement", "receipt", or "unknown".
        - 'vendor': The merchant, store, or client name.
        - 'description': A brief description of the transaction.
        - 'date': The transaction date in DD/MM/YYYY format. Expect dates in the format DD/MM/YYYY and with year 2025. Be careful of inverting the order.Set to null only if completely absent.
        - 'total': The total of all items on the receipt as a float with two decimal places. The total should be identified by the bold "TOTAL" label in uppercase and should be the final amount. Avoid returning the value of label "Sous-Total" since it means the subtotal.
        - 'payment_method': The payment type used. If the receipt explicitly states "Credit Card", "Cash", or "Electronic Transfer", use those. The label "Comptant" means "Cash". If the receipt contains "E-TRANSFERT", it indicates "Electronic Transfer". If the receipt contains "CARTE DE CRÉDIT" or "CB", it indicates "Credit Card".
        
        CRITICAL EXTRACTION GUIDELINES:
        You MUST first internally locate:
        (1) the line containing the date
        (2) all lines containing monetary values ($) with labels
        (3) the line that explicitly represents TOTAL

        Do not compute the final JSON until these are identified.

        CRITICAL NOISE EXCLUSION:
        If the image is unrelated noise (such as a pet, scenery, or meme), you must set 'category' to "unknown" and every other attribute to none
        
        
        JSON schema expected:
        {   
            "category": "receipt" or "invoice" or "bank_statement" or "unknown",
            "vendor": string or null,
            "description": string or null,
            "date": string or null,
            "total": string or null,
            "payment_method": string or null
        }
        
        <|im_start|>user
        <|vision_start|><|image_pad|><|vision_end|>
        Please extract the transaction details for the receipt.
        <|im_end|>
        <|im_start|>assistant
        """
               
  

        inputs = tf_processor(
            text=[ONE_SHOT_PROMPT],
            images=[image],
            padding=True,
            return_tensors="pt"
        ).to(tf_model.device)


        print("🧠 Model is thinking ...")
        generated_ids = tf_model.generate(
            **inputs, 
            max_new_tokens=512,
            do_sample=False # Keep it deterministic
        )
        
        
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        raw_output = tf_processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )[0]
        
        print(raw_output)    
               
        
        
        return ExtractionResult(
            source_file=image_path.name,
            records=[clean_and_validate_raw_output(raw_output, image_path.name)]
        )
        
def clean_and_validate_raw_output(raw_output_str: str, image_name: str) -> Transaction:  
    fallback_tx = Transaction(
        source_file=image_name,
        category=TransactionCategory.UNKNOWN,
        vendor=None,
        description=None,
        date=None,
        amount=None,
        payment_method=PaymentMethod.UNKNOWN,
        warnings=[]
    )

    clean_str = raw_output_str.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(clean_str)
        if not isinstance(data, dict):
            return fallback_tx
    except (json.JSONDecodeError, TypeError):
        return fallback_tx
    
    raw_cat = str(data.get("category", ""))
    try:
        category = TransactionCategory(raw_cat.strip().lower())
    except ValueError:
        category = TransactionCategory.UNKNOWN

    vendor = str(data.get("vendor")) if data.get("vendor") is not None else None
    description = str(data.get("description")) if data.get("description") is not None else None


    raw_amount = data.get("total")
    clean_amount = None
    if raw_amount is not None:
        amount_match = re.search(r"[-+]?\d*\.\d+|\d+", str(raw_amount))
        if amount_match:
            try:
                clean_amount = float(amount_match.group())
            except ValueError:
                clean_amount = None

    raw_payment = str(data.get("payment_method") or "").lower()
    if "transfer" in raw_payment or "virement" in raw_payment:
        payment_method = PaymentMethod.E_TRANSFER
    elif "credit" in raw_payment or "carte" in raw_payment or "cb" in raw_payment:
        payment_method = PaymentMethod.CREDIT_CARD
    elif "cash" in raw_payment or "comptant" in raw_payment:
        payment_method = PaymentMethod.CASH
    else:
        payment_method = PaymentMethod.UNKNOWN


    raw_date = data.get("date")
    formatted_date = None
    if raw_date and str(raw_date).lower() != "null":
        date_str = str(raw_date).strip()
        parts = date_str.split(' ')
        if parts and parts[0]:
            try:
                formatted_date = datetime.datetime.strptime(parts[0], "%d/%m/%Y").date()
            except ValueError:
                formatted_date = None

    try:
        return Transaction(
            source_file=image_name,
            category=category,
            vendor=vendor,
            description=description,
            date=formatted_date,
            amount=clean_amount,
            payment_method=payment_method,
            warnings=[]
        )
    except Exception:
        return fallback_tx


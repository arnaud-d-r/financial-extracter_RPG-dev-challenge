from __future__ import annotations

import os
from pathlib import Path
from unittest import result

from click import prompt
import torch

from .models import  Transaction, ExtractionResult, TransactionCategory
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


print("🚀 Loading local vLLM engine via Outlines...")
model_name = "Qwen/Qwen2-VL-2B-Instruct"

tf_model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_name,
    device_map="auto",
    attn_implementation="sdpa",  # Scaled Dot-Product Attention (Fast)
    torch_dtype=torch.bfloat16,  # Crisp, non-degraded floating-point accuracy
)

tf_processor = AutoProcessor.from_pretrained(
    model_name,
    min_pixels=1024*28*28,
    max_pixels=2048*28*28
)

model = outlines.from_transformers(tf_model, tf_processor)

def parse_images(path: str | Path, category: TransactionCategory = TransactionCategory.RECEIPT) -> ExtractionResult:
    image_path = Path(path)


    
    with Image.open(image_path) as image:
        ONE_SHOT_PROMPT = """<|im_start|>system
        You are a precise forensic financial audit assistant specializing in data extraction from messy freelancer documents. Your task is to extract financial transaction data from images into a strict JSON schema.

        EXPECTED FIELD LOGIC & SEMANTICS:
        - 'source_file': The exact filename string provided to you in the user prompt.
        - 'category': The type of document. Must be exactly one of: "invoice", "bank_statement", "receipt", or "unknown".
        - 'vendor': The merchant, store, or client name.
        - 'description': Brief summary of what was bought or line-item details.
        - 'date': The transaction date in YYYY-MM-DD format. Expect dates in the format DD/MM/YYYY and with year 2025. Be careful of inverting the order.Set to null only if completely absent.
        - 'amount': The final amount paid, as a float. Should be a number preceded by $. Only consider labels containing: "TOTAL", "AMOUNT DUE", "BALANCE DUE", "GRAND TOTAL". Ignore labels containing: "SUBTOTAL", "SUB-TOTAL", "BEFORE TAX". Set to null if not found or if the value is not a valid number.
        - 'currency': Default to "CAD" unless explicitly specified otherwise.
        - 'invoice_paid_date': The date the invoice was settled (YYYY-MM-DD). This must be set to null if the category is a receipt or bank statement.
        - 'payment_method': The payment type used. Must be exactly one of: "credit_card", "cash", "electronic_transfer", or "unknown".
        - 'warnings': An empty array [] by default.
        
        CRITICAL EXTRACTION GUIDELINES:
        You MUST first internally locate:
        (1) the line containing the date
        (2) all lines containing monetary values with labels
        (3) the line that explicitly represents FINAL TOTAL

        Do not compute the final JSON until these are identified.

        CRITICAL NOISE EXCLUSION:
        If the image is unrelated noise (such as a pet, scenery, or meme), you must set 'category' to "unknown", 'warnings' to ["invalid_category"], and every other optional field strictly to null.
        

        Please extract the transaction details for the file 'McDonald.png'. It should follow this JSON schema:
        
        Example of expected output for a McDonald's cash receipt:
        {{
            "source_file": "restaurant.png",
            "category": "receipt",
            "vendor": "McDonald's",
            "description": null,
            "date": "2025-07-20",
            "amount": 15.99,
            "currency": "CAD",
            "invoice_paid_date": null,
            "payment_method": "cash",
            "warnings": []
        }}

        <|im_start|>user
        <|vision_start|><|image_pad|><|vision_end|>
        Please extract the transaction details for the file '{file_name}'.
        <|im_end|>
        <|im_start|>assistant
        """
                    
        formatted_prompt = ONE_SHOT_PROMPT.format(
            file_name=image_path.name
        )
        
        generator = outlines.Generator(model, Transaction)
        extracted_transaction = generator(
            [formatted_prompt, OutlinesImage(image)],
            max_new_tokens=1024,
        )

        if isinstance(extracted_transaction, str):
            extracted_transaction = Transaction.model_validate_json(extracted_transaction)

        
        return ExtractionResult(
            source_file=image_path.name,
            records=[extracted_transaction]
        )
        


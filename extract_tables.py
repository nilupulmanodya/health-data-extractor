import re
import json
import traceback # For detailed error logging

def clean_cell(cell_text):
    cleaned = cell_text.replace("<br>", " ").strip()
    return re.sub(r'\s+', ' ', cleaned)

def extract_individual_tables_from_file(content):

    page_start_pattern = r"(?:(?:####\s*)?\*\*INSTITUTE ON AGING SOUTHERN CALIFORNIA LLC.*?SAN BERNARDINO, CA 92408 \d+\*\*)"
    matches = list(re.finditer(page_start_pattern, content, flags=re.MULTILINE | re.DOTALL))
    
    table_strings = []
    if not matches:
        if "|" in content and ("Member #" in content or "Claim#" in content or "Claim<br>#" in content):
            return [content.strip()] 
        print("Warning: No standard page start patterns found in the input file.")
        return []

    for i, match in enumerate(matches):
        start_pos = match.start()
        end_pos = matches[i+1].start() if (i + 1) < len(matches) else len(content)
        table_block = content[start_pos:end_pos].strip()
        if table_block: 
            table_strings.append(table_block)
    return table_strings

TARGET_CLAIM_HEADERS = [
    "Claim #", "Line/Ver#", "Received Date", "Service From", "Service To",
    "Proc", "Mod", "Qty", "Amount Billed", "Amount Allowed", "Not Covered",
    "Copay/Coins", "Deduct Amount", "Withhold Amount", "Net Paid", "ST",
    "Reason", "Interest", "Adjust"
]
NUMERIC_FINANCIAL_HEADERS = [
    "Amount Billed", "Amount Allowed", "Not Covered", "Copay/Coins", 
    "Deduct Amount", "Withhold Amount", "Net Paid", "Interest"
]

def extract_name_from_cell_content(cell_content, name_pattern_regex):
    name_parts_test = cell_content.split()
    potential_name_str = cell_content 
    
    if len(name_parts_test) > 1: 
        last_part = name_parts_test[-1]
        is_qty_like = last_part.replace('.', '', 1).isdigit() and "." in last_part
        is_short_alphanum_code_like = (len(last_part) <= 2 and last_part.isalnum() and not (len(last_part) == 1 and last_part.isalpha()))

        if is_qty_like or is_short_alphanum_code_like:
            temp_name_try = " ".join(name_parts_test[:-1])
            if temp_name_try and ("," in temp_name_try or len(temp_name_try.split()) > 1 or len(temp_name_try) > 3):
                potential_name_str = temp_name_try

    if name_pattern_regex.match(potential_name_str):
        name_check_parts = potential_name_str.split()
        if "," in potential_name_str or len(name_check_parts) > 1:
            if not (len(name_check_parts) == 1 and potential_name_str.isupper() and len(potential_name_str) <= 3):
                 return potential_name_str
    return ""

def parse_eob_table(table_string, ongoing_member_context=None):
    lines = table_string.strip().split('\n')
    members_completed_this_block = [] 
    current_member_info = ongoing_member_context 
    
    source_claim_headers_t1 = ["Claim#", "Line/Ver#", "Received Date", "From", "Service Period/Date To", "Proc", "Mod", "Qty", "Amount Billed", "Amount Allowed", "Not Covered", "Copay/Coins", "Deduct Amount", "Withhold Amount", "Net Paid", "S T", "Reason", "Interest", "Adjust"]
    source_claim_headers_t2 = ["Claim#", "Line/Ver#", "Received Date", "From", "Service Period/Date To", "Proc", "Mod", "Qty", "Amount Billed", "Amount Allowed", "Not Covered", "Copay/Coins", "Deduct Amount", "Withhold Amount", "Net Paid", "S T Reason", "Interest", "Adjust"]
    
    table_type = 1 
    header_line_for_type_detection = ""
    for line_raw_detect in lines:
        if ("Claim#" in line_raw_detect or "Claim<br>#" in line_raw_detect) and ("Proc" in line_raw_detect) and ("Amount<br>Billed" in line_raw_detect or "Amount Billed" in line_raw_detect):
            header_line_for_type_detection = clean_cell(line_raw_detect); break
    if "S T Reason" in header_line_for_type_detection or "S<br>T<br>Reason" in table_string : table_type = 2
    current_source_claim_headers = source_claim_headers_t1 if table_type == 1 else source_claim_headers_t2
    
    name_pattern_re = re.compile(r"^[A-Z,\s']{3,}[A-Z]$") 
    provider_name_identifier = "INSTITUTE ON AGING SOUTHERN CALIFORNIA LLC"
    name_for_next_member_from_totals = None 

    for line_idx, line_raw in enumerate(lines):
        try:
            line = line_raw.strip()
            patient_name_candidate_on_curr_line = "" 
            is_col_header_def_line1 = ("Member #" in line_raw and "Line of Business" in line_raw and "Patient Name" in line_raw)
            is_col_header_def_line2 = (("Claim#" in line_raw or "Claim<br>#" in line_raw) and ("Line/<br>Ver#" in line_raw or "Line/Ver#" in line_raw) and ("Amount<br>Billed" in line_raw or "Amount Billed" in line_raw))

            if not line or line.startswith('|--') or is_col_header_def_line1 or is_col_header_def_line2 or "Page No.:" in line_raw or "Remittance Advice" in line_raw:
                is_simple_separator = line.strip().startswith("|") and line.strip().endswith("|") and len(line.split("|")) > 2
                is_meaningful_content = any(c.strip() for c in line.split('|')[1:-1] if c.strip())
                if not (is_simple_separator and is_meaningful_content):
                    if provider_name_identifier in line_raw and "SAN BERNARDINO, CA" in line_raw : continue
                    if not (line.strip().startswith("|") and line.strip().endswith("|") and len(line.split("|")) > 2): continue
                else: continue
            cells_raw = line.split('|')
            if len(cells_raw) > 1 and not cells_raw[0].strip(): cells_raw = cells_raw[1:]
            if len(cells_raw) > 1 and not cells_raw[-1].strip(): cells_raw = cells_raw[:-1]
            cells = [clean_cell(c) for c in cells_raw]
            if not any(cells) or len(cells) < 2: continue
            
            is_new_member_line_flag = False
            potential_member_id_cell_cleaned = cells[0]
            provider_name_candidate = ""
            lob_candidate = ""
            c0_is_member_id_like = (("Medi-Cal" in potential_member_id_cell_cleaned and any(char.isdigit() for char in potential_member_id_cell_cleaned.replace("Medi-Cal","").replace(" ",""))) or (potential_member_id_cell_cleaned.replace(" ", "").isdigit() and len(potential_member_id_cell_cleaned.replace(" ", "")) >= 10))
            
            for cell_idx, cell_content in enumerate(cells):
                if provider_name_identifier in cell_content: provider_name_candidate = provider_name_identifier
                extracted_name = extract_name_from_cell_content(cell_content, name_pattern_re)
                if extracted_name and provider_name_identifier not in extracted_name and extracted_name not in TARGET_CLAIM_HEADERS and extracted_name not in ["Patient Name", "Line of Business", "Provider Name", "Medi-Cal", "Claim Totals :", "Member Totals :"]:
                    if len(extracted_name) > len(patient_name_candidate_on_curr_line): patient_name_candidate_on_curr_line = extracted_name
                if "Medi-Cal" == cell_content.strip() and cell_idx < 4 : lob_candidate = "Medi-Cal"
            if not lob_candidate and "Medi-Cal" in potential_member_id_cell_cleaned: lob_candidate = "Medi-Cal"
            if not lob_candidate and any("Medi-Cal" in c for c in cells[:4]): lob_candidate = "Medi-Cal"
            
            name_to_use_for_new_member = patient_name_candidate_on_curr_line
            was_name_carried = False
            if not name_to_use_for_new_member and name_for_next_member_from_totals and c0_is_member_id_like:
                name_to_use_for_new_member = name_for_next_member_from_totals
                was_name_carried = True 
            if c0_is_member_id_like and name_to_use_for_new_member: is_new_member_line_flag = True
            
            _current_line_sets_next_name = None
            if "Member Totals :" in line_raw:
                name_on_this_totals_line = "" 
                for cell_content_for_totals_check in cells:
                    if "Member Totals :" in cell_content_for_totals_check:
                        parts_after_totals = cell_content_for_totals_check.split("Member Totals :", 1)
                        if len(parts_after_totals) > 1:
                            potential_name_str_from_totals = parts_after_totals[1].strip()
                            extracted_name = extract_name_from_cell_content(potential_name_str_from_totals, name_pattern_re)
                            if extracted_name: name_on_this_totals_line = extracted_name; break 
                if current_member_info :
                    is_already_added = False
                    if members_completed_this_block and members_completed_this_block[-1] is current_member_info: is_already_added = True
                    if not is_already_added: members_completed_this_block.append(current_member_info)
                current_member_info = None 
                if name_on_this_totals_line: _current_line_sets_next_name = name_on_this_totals_line
            
            if _current_line_sets_next_name is not None: name_for_next_member_from_totals = _current_line_sets_next_name
            elif was_name_carried: name_for_next_member_from_totals = None 
            else: name_for_next_member_from_totals = None
            
            if "Member Totals :" in line_raw: continue

            if is_new_member_line_flag:
                if current_member_info: 
                    is_already_added = False
                    if members_completed_this_block and members_completed_this_block[-1] is current_member_info: is_already_added = True
                    if not is_already_added and current_member_info.get("Member #"): members_completed_this_block.append(current_member_info)
                member_id_val = potential_member_id_cell_cleaned; id_parts = potential_member_id_cell_cleaned.split()
                if len(id_parts) > 1 and id_parts[0].isdigit() and len(id_parts[0]) >= 10 and id_parts[1].isdigit() and (len(id_parts[1]) >= 6 and len(id_parts[1]) <=10): member_id_val = id_parts[0]
                current_member_info = {"Member #": member_id_val, "Line of Business": lob_candidate if lob_candidate else "Medi-Cal", "Patient Name": name_to_use_for_new_member, "Provider Name": provider_name_candidate if provider_name_candidate else provider_name_identifier, "claims": []}
            
            is_claim_data_present_on_this_line = False
            if current_member_info: 
                c0_val = cells[0]; c1_val = cells[1] if len(cells) > 1 else ""; c0_parts = c0_val.split()
                member_id_str = current_member_info.get("Member #", "###NEVERMATCH###"); member_id_first_part = member_id_str.split()[0] if member_id_str else "###NEVERMATCH###"
                is_c0_simple_claim_num = c0_val.isdigit() and (len(c0_val) == 9 or len(c0_val) == 10)
                if is_c0_simple_claim_num and (not member_id_first_part or not member_id_first_part.startswith(c0_val)): is_claim_data_present_on_this_line = True
                if not is_claim_data_present_on_this_line and is_new_member_line_flag and len(c0_parts) > 1 and (c0_parts[0] == member_id_first_part or potential_member_id_cell_cleaned.startswith(member_id_first_part)) and c0_parts[-1].isdigit() and (len(c0_parts[-1]) >=6 and len(c0_parts[-1]) <=10): is_claim_data_present_on_this_line = True
                if not is_claim_data_present_on_this_line and c1_val.isdigit() and len(c1_val) == 6 and len(cells) > 5: is_claim_data_present_on_this_line = True
            
            if is_new_member_line_flag and not is_claim_data_present_on_this_line: continue 
            if "Totals :" in line_raw and "Member Totals :" not in line_raw : continue 
            if "Patient Acct. #" in line_raw:
                if current_member_info and current_member_info["claims"]:
                    account_info = "";
                    for cell_val in cells:
                        if "Patient Acct. #" in cell_val: account_info = cell_val.split("Patient Acct. #")[-1].strip(); break
                    if account_info : current_member_info["claims"][-1]["Patient Acct. #"] = account_info
                continue

            if is_claim_data_present_on_this_line and len(cells) >= 5 and current_member_info:
                source_claim_details = {}
                if is_new_member_line_flag: 
                    current_cell_idx = 0; c0_content = cells[current_cell_idx].strip(); c0_parts = c0_content.split()
                    if len(c0_parts) > 1 and c0_parts[-1].isdigit() and (len(c0_parts[-1]) >= 6 and len(c0_parts[-1]) <= 10): source_claim_details["Claim#"] = c0_parts[-1]
                    elif c0_parts[0].isdigit() and (len(c0_parts[0]) >= 6 and len(c0_parts[0]) <= 10) and not (current_member_info and c0_parts[0].startswith(current_member_info.get("Member #", "###").split()[0]) and len(c0_parts) == 1) : source_claim_details["Claim#"] = c0_parts[0]
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx and cells[current_cell_idx].strip().isdigit() and len(cells[current_cell_idx].strip()) == 6: source_claim_details["Line/Ver#"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx and re.match(r"\d{2}/\d{2}/\d{4}", cells[current_cell_idx].strip()): source_claim_details["Received Date"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx:
                        from_field_content = cells[current_cell_idx].strip(); from_parts = from_field_content.split()
                        if from_parts[0].upper() == "MEDI-CAL" and len(from_parts) > 1 and re.match(r"\d{2}/\d{2}/\d{4}", from_parts[-1]): source_claim_details["From"] = from_parts[-1]
                        elif re.match(r"\d{2}/\d{2}/\d{4}", from_parts[0]): source_claim_details["From"] = from_parts[0]
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx and re.match(r"\d{2}/\d{2}/\d{4}", cells[current_cell_idx].strip()): source_claim_details["Service Period/Date To"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx and re.match(r"^[A-Z0-9]{4,5}$", cells[current_cell_idx].strip()): source_claim_details["Proc"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    
                    # MODIFIED Mod Parsing for Combined Lines
                    if len(cells) > current_cell_idx:
                        mod_cell_content = cells[current_cell_idx].strip()
                        if re.match(r"^[A-Z0-9]{1,2}$", mod_cell_content): # Direct match: cell is only Mod
                            source_claim_details["Mod"] = mod_cell_content
                        else: # Check for "NAME MOD" pattern
                            mod_parts = mod_cell_content.split()
                            if len(mod_parts) > 1:
                                potential_mod = mod_parts[-1]
                                # Extracted name for the current member (name_to_use_for_new_member) was from this cell or previous
                                # If current cell content starts with the member's name and ends with a Mod-like code
                                if name_to_use_for_new_member and mod_cell_content.startswith(name_to_use_for_new_member) and \
                                   re.match(r"^[A-Z0-9]{1,2}$", potential_mod):
                                    # Ensure the part before potential_mod is indeed the name
                                    if mod_cell_content == f"{name_to_use_for_new_member} {potential_mod}".strip():
                                         source_claim_details["Mod"] = potential_mod
                    current_cell_idx += 1 # End Mod Parsing
                                        
                    if len(cells) > current_cell_idx:
                        qty_candidate_cell_content = cells[current_cell_idx].strip(); qty_parts = qty_candidate_cell_content.split()
                        if len(qty_parts) > 0:
                            potential_qty_str = qty_parts[-1]
                            # If the name was in the Mod cell, Qty should be standalone here.
                            # If Name+Mod was in Mod cell, Qty cell is next.
                            # If Name+Qty was in Qty cell (Mod cell was standalone or empty), this handles it.
                            if potential_qty_str.replace(".", "", 1).isdigit() and "." in potential_qty_str: 
                                source_claim_details["Qty"] = potential_qty_str
                            # Case: ALI, KHALIL<br>U8 (in Mod pos), Qty 1.00 (in Qty pos) -> Qty is taken from Qty pos
                            # Case: AGUILAR, ESTHER<br>1.00 (in Qty pos) -> Qty taken here if Mod pos was empty
                    current_cell_idx += 1 
                    
                    idx_in_source_headers_for_amt_billed = next((idx_sh for idx_sh, sh_name in enumerate(current_source_claim_headers) if sh_name == "Amount Billed"), -1)
                    if idx_in_source_headers_for_amt_billed != -1:
                        for i_sh_offset, source_header_name in enumerate(current_source_claim_headers[idx_in_source_headers_for_amt_billed:]):
                            cell_idx_for_this_sh_data = current_cell_idx + i_sh_offset
                            if cell_idx_for_this_sh_data < len(cells):
                                value_to_assign = cells[cell_idx_for_this_sh_data].strip()
                                if source_header_name in NUMERIC_FINANCIAL_HEADERS and provider_name_identifier in value_to_assign:
                                    temp_val = value_to_assign.replace(provider_name_identifier, "").strip()
                                    if temp_val.replace('.', '', 1).replace('-', '', 1).isdigit() or not temp_val : value_to_assign = temp_val
                                source_claim_details[source_header_name] = value_to_assign
                            else: source_claim_details[source_header_name] = ""
                else: 
                    temp_claim_cells = list(cells) 
                    for i, header_name in enumerate(current_source_claim_headers):
                        if i < len(temp_claim_cells):
                            value_to_assign = temp_claim_cells[i].strip()
                            if header_name in NUMERIC_FINANCIAL_HEADERS and provider_name_identifier in value_to_assign:
                                temp_val = value_to_assign.replace(provider_name_identifier, "").strip()
                                if temp_val.replace('.', '', 1).replace('-', '', 1).isdigit() or not temp_val: value_to_assign = temp_val
                            source_claim_details[header_name] = value_to_assign
                        else: source_claim_details[header_name] = ""
                
                final_claim_output = {hdr: "" for hdr in TARGET_CLAIM_HEADERS} 
                final_claim_output["Claim #"] = source_claim_details.get("Claim#", ""); final_claim_output["Line/Ver#"] = source_claim_details.get("Line/Ver#", ""); final_claim_output["Received Date"] = source_claim_details.get("Received Date", ""); final_claim_output["Service From"] = source_claim_details.get("From", ""); final_claim_output["Service To"] = source_claim_details.get("Service Period/Date To", ""); final_claim_output["Proc"] = source_claim_details.get("Proc", ""); final_claim_output["Mod"] = source_claim_details.get("Mod", ""); final_claim_output["Qty"] = source_claim_details.get("Qty", ""); final_claim_output["Amount Billed"] = source_claim_details.get("Amount Billed", ""); final_claim_output["Amount Allowed"] = source_claim_details.get("Amount Allowed", ""); final_claim_output["Not Covered"] = source_claim_details.get("Not Covered", ""); final_claim_output["Copay/Coins"] = source_claim_details.get("Copay/Coins", ""); final_claim_output["Deduct Amount"] = source_claim_details.get("Deduct Amount", ""); final_claim_output["Withhold Amount"] = source_claim_details.get("Withhold Amount", ""); final_claim_output["Net Paid"] = source_claim_details.get("Net Paid", ""); final_claim_output["Adjust"] = source_claim_details.get("Adjust", "")
                original_interest_val = source_claim_details.get("Interest", ""); final_claim_output["Interest"] = original_interest_val
                if table_type == 1:
                    st_val, reason_val = source_claim_details.get('S T', ''), source_claim_details.get('Reason', ''); st_parts = st_val.split(maxsplit=1)
                    if len(st_parts) > 1 and (not reason_val or reason_val == st_parts[1] or reason_val.startswith(st_parts[1])): final_claim_output['ST'], final_claim_output['Reason'] = st_parts[0], st_parts[1]
                    else: final_claim_output['ST'], final_claim_output['Reason'] = st_val, reason_val
                else: 
                    st_reason_val = source_claim_details.get('S T Reason', ''); parts = st_reason_val.split(maxsplit=1); final_claim_output['ST'] = parts[0] if parts else st_reason_val
                    if len(parts) > 1: final_claim_output['Reason'] = parts[1]
                    elif original_interest_val and not original_interest_val.replace('.','',1).isdigit() and not original_interest_val.isspace() and original_interest_val != "0.00": final_claim_output['Reason'], final_claim_output['Interest'] = original_interest_val, ""
                    else: final_claim_output['Reason'] = ""
                current_member_info["claims"].append(final_claim_output)
        except Exception as e:
            print(f"CRITICAL ERROR processing line {line_idx + 1} in table block: '{line_raw}'")
            print(f"Exception details: {type(e).__name__} - {e}")
            traceback.print_exc()
            continue 
    return members_completed_this_block, current_member_info

def extract_tables(unstructured_text, output_json_path=None):

    table_strings = extract_individual_tables_from_file(unstructured_text)
    all_members_data = []
    carried_over_member_info_state = None 
    last_block_completed_members_count = 0

    for i, table_str in enumerate(table_strings):
        if not table_str.strip(): 
            print(f"Skipping empty table block {i+1}")
            continue
        
        completed_members_in_block, carried_over_member_info_state = parse_eob_table(table_str, carried_over_member_info_state)
        all_members_data.extend(completed_members_in_block)
        last_block_completed_members_count = len(completed_members_in_block)

    if carried_over_member_info_state: 
        if carried_over_member_info_state.get("claims") or \
           (last_block_completed_members_count == 0 and len(all_members_data) == 0 and len(table_strings) > 0):
            all_members_data.append(carried_over_member_info_state)

    if output_json_path:
        try:
            with open(output_json_path, 'w', encoding='utf-8') as json_file:
                json.dump(all_members_data, json_file, indent=2)
            print(f"\nSuccessfully saved parsed data to '{output_json_path}'")
        except Exception as e:
            print(f"\nError saving to JSON file: {str(e)}")
    
    print(f"\n--- Total Members Parsed: {len(all_members_data)} ---")
    return all_members_data

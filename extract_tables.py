import re
import json
import traceback # For detailed error logging

def clean_cell(cell_text):
    cleaned = cell_text.replace("<br>", " ").strip()
    return re.sub(r'\s+', ' ', cleaned)

def extract_individual_tables_from_file(content):

    if not content.strip():
        print(f"Error: Content is empty or whitespace only.")
        return []

    page_start_pattern = r"^(?:(?:####\s*)?\*\*INSTITUTE ON AGING SOUTHERN CALIFORNIA LLC)"
    
    matches = []
    try:
        matches = list(re.finditer(page_start_pattern, content, flags=re.MULTILINE))
    except Exception as e:
        print(f"Error during regex finditer for page_start_pattern: {e}")
        return [] 

    table_strings = []
    if not matches:
        if "|" in content and ("Member #" in content or "Claim#" in content or "Claim<br>#" in content):
            return [content.strip()]
        else:
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
DATE_PATTERN_RE = r"\d{2}/\d{2}/\d{4}"

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
        cleaned_line_detect = clean_cell(line_raw_detect)
        if ("Claim#" in cleaned_line_detect) and \
           ("Proc" in cleaned_line_detect) and \
           ("Amount Billed" in cleaned_line_detect):
            header_line_for_type_detection = cleaned_line_detect
            break
    if "S T Reason" in header_line_for_type_detection: table_type = 2
    current_source_claim_headers = source_claim_headers_t1 if table_type == 1 else source_claim_headers_t2

    name_pattern_re = re.compile(r"^[A-Z,\s']{3,}[A-Z]$") 
    provider_name_identifier = "INSTITUTE ON AGING SOUTHERN CALIFORNIA LLC"
    name_for_next_member_from_totals = None

    proc_regex = r"^[A-Z0-9]{4,5}$"
    mod_regex = r"^[A-Z0-9]{1,2}$"
    qty_check = lambda s: (s.replace(".", "", 1).replace("-","").isdigit() and "." in s) or s.replace("-","").isdigit()


    for line_idx, line_raw in enumerate(lines):
        try:
            line = line_raw.strip()
            _current_line_sets_next_name = None 
            was_name_carried_for_current_line = False 

            if line.startswith("Member Totals :") and not '|' in line:
                if current_member_info:
                    is_already_added = any(m is current_member_info for m in members_completed_this_block)
                    if not is_already_added and current_member_info.get("Member #"):
                        members_completed_this_block.append(current_member_info)
                current_member_info = None
                _current_line_sets_next_name = None 
                name_for_next_member_from_totals = None 
                continue

            patient_name_candidate_on_curr_line = ""
            is_col_header_def_line1 = ("Member #" in line and "Line of Business" in line and "Patient Name" in line)
            is_col_header_def_line2 = (("Claim#" in line or "Claim<br>#" in line) and \
                                       ("Line/<br>Ver#" in line or "Line/Ver#" in line) and \
                                       ("Amount<br>Billed" in line or "Amount Billed" in line))

            non_data_prefixes = ("**INSTITUTE ON AGING SOUTHERN CALIFORNIA LLC", "EFT-", "Check No.:", "Check Date:", "Check Amount:")
            if not line or line.startswith('|--') or is_col_header_def_line1 or is_col_header_def_line2 or \
               "Page No.:" in line or "Remittance Advice" in line or \
               any(line.startswith(p) for p in non_data_prefixes) or \
               (line.count('|') < 2 and not (line.startswith("Member Totals :") and not '|' in line)):
                continue
            
            cells_raw = line.split('|')
            start_index = 0
            if cells_raw and not cells_raw[0].strip(): start_index = 1
            end_index = len(cells_raw)
            if cells_raw and end_index > start_index and not cells_raw[-1].strip(): end_index -=1
            cells_raw = cells_raw[start_index:end_index]
            cells = [clean_cell(c) for c in cells_raw]

            if not any(c.strip() for c in cells if c.strip()):
                continue
            
            # Removed Patient Acct. # specific extraction logic from here

            is_new_member_line_flag = False
            potential_member_id_cell_cleaned = cells[0] if cells else ""
            provider_name_candidate = ""
            lob_candidate = ""
            c0_is_member_id_like = (
                ("Medi-Cal" in potential_member_id_cell_cleaned and any(char.isdigit() for char in potential_member_id_cell_cleaned.replace("Medi-Cal","").replace(" ",""))) or
                (potential_member_id_cell_cleaned.replace(" ", "").isdigit() and len(potential_member_id_cell_cleaned.replace(" ", "")) >= 12) or
                (potential_member_id_cell_cleaned.replace(" ", "").isdigit() and len(potential_member_id_cell_cleaned.replace(" ", "")) >= 10 and not potential_member_id_cell_cleaned.startswith("00"))
            )

            for cell_idx, cell_content in enumerate(cells):
                if provider_name_identifier in cell_content: provider_name_candidate = provider_name_identifier
                extracted_name = extract_name_from_cell_content(cell_content, name_pattern_re)
                if extracted_name and provider_name_identifier not in extracted_name and \
                   extracted_name not in TARGET_CLAIM_HEADERS and \
                   extracted_name not in ["Patient Name", "Line of Business", "Provider Name", "Medi-Cal", "Claim Totals :", "Member Totals :"]:
                    if len(extracted_name) > len(patient_name_candidate_on_curr_line):
                        patient_name_candidate_on_curr_line = extracted_name
                if "Medi-Cal" == cell_content.strip() and cell_idx < 4 : lob_candidate = "Medi-Cal"

            if not lob_candidate and "Medi-Cal" in potential_member_id_cell_cleaned: lob_candidate = "Medi-Cal"
            if not lob_candidate and any("Medi-Cal" in c for c in cells[:4]): lob_candidate = "Medi-Cal"

            name_to_use_for_new_member = patient_name_candidate_on_curr_line
            if not name_to_use_for_new_member and name_for_next_member_from_totals and c0_is_member_id_like:
                name_to_use_for_new_member = name_for_next_member_from_totals
                was_name_carried_for_current_line = True
            if c0_is_member_id_like and name_to_use_for_new_member:
                is_new_member_line_flag = True

            if "Member Totals :" in line_raw and '|' in line_raw: 
                name_on_this_totals_line_piped = ""
                for cell_content_for_totals_check in cells:
                    if "Member Totals :" in cell_content_for_totals_check:
                        parts_after_totals = cell_content_for_totals_check.split("Member Totals :", 1)
                        if len(parts_after_totals) > 1:
                            potential_name_str_from_totals = parts_after_totals[1].strip()
                            extracted_name = extract_name_from_cell_content(potential_name_str_from_totals, name_pattern_re)
                            if extracted_name: name_on_this_totals_line_piped = extracted_name; break
                if current_member_info :
                    is_already_added = any(m is current_member_info for m in members_completed_this_block)
                    if not is_already_added and current_member_info.get("Member #"):
                        members_completed_this_block.append(current_member_info)
                current_member_info = None
                if name_on_this_totals_line_piped: _current_line_sets_next_name = name_on_this_totals_line_piped
            
            if _current_line_sets_next_name is not None:
                name_for_next_member_from_totals = _current_line_sets_next_name
            elif was_name_carried_for_current_line: 
                name_for_next_member_from_totals = None 
            elif ("Member Totals :" in line_raw and '|' in line_raw and _current_line_sets_next_name is None) :
                name_for_next_member_from_totals = None

            if "Member Totals :" in line_raw and '|' in line_raw : continue
            if "Claim Totals :" in line_raw : continue 

            if is_new_member_line_flag:
                if current_member_info: 
                    is_already_added = any(m is current_member_info for m in members_completed_this_block)
                    if not is_already_added and current_member_info.get("Member #"):
                        members_completed_this_block.append(current_member_info)
                member_id_val = potential_member_id_cell_cleaned; id_parts = potential_member_id_cell_cleaned.split()
                if len(id_parts) > 1 and id_parts[0].isdigit() and len(id_parts[0]) >= 10 and \
                   id_parts[1].isdigit() and (len(id_parts[1]) >= 6 and len(id_parts[1]) <=10):
                    member_id_val = id_parts[0]
                current_member_info = {"Member #": member_id_val, "Line of Business": lob_candidate if lob_candidate else "Medi-Cal", "Patient Name": name_to_use_for_new_member, "Provider Name": provider_name_candidate if provider_name_candidate else provider_name_identifier, "claims": []}

            is_claim_data_present_on_this_line = False
            if current_member_info: 
                c0_val = cells[0] if cells else ""; c1_val = cells[1] if len(cells) > 1 else ""; c0_parts = c0_val.split()
                member_id_str = current_member_info.get("Member #", "###NEVERMATCH###");
                member_id_first_part = member_id_str.split()[0] if member_id_str else "###NEVERMATCH###"
                is_c0_simple_claim_num = c0_val.isdigit() and (len(c0_val) >= 6 and len(c0_val) <= 10) 
                
                if is_c0_simple_claim_num and (not member_id_first_part or not member_id_first_part.startswith(c0_val)):
                    is_claim_data_present_on_this_line = True
                if not is_claim_data_present_on_this_line and is_new_member_line_flag and \
                   len(c0_parts) > 1 and \
                   (c0_parts[0] == member_id_first_part or potential_member_id_cell_cleaned.startswith(member_id_first_part)) and \
                   c0_parts[-1].isdigit() and (len(c0_parts[-1]) >=6 and len(c0_parts[-1]) <=10):
                    is_claim_data_present_on_this_line = True
                if not is_claim_data_present_on_this_line and c1_val.isdigit() and len(c1_val) == 6 and len(cells) > 5: 
                    is_claim_data_present_on_this_line = True
            
            if is_new_member_line_flag and not is_claim_data_present_on_this_line: continue
            
            if is_claim_data_present_on_this_line and len(cells) >= 5 and current_member_info:
                source_claim_details = {}
                current_cell_idx = 0 
                cell_idx_iter = 0    

                if is_new_member_line_flag: 
                    c0_content = cells[current_cell_idx].strip(); c0_parts = c0_content.split()
                    claim_num_candidate = ""
                    if len(c0_parts) > 1 and c0_parts[-1].isdigit() and (len(c0_parts[-1]) >= 6 and len(c0_parts[-1]) <= 10): claim_num_candidate = c0_parts[-1]
                    elif c0_parts[0].isdigit() and (len(c0_parts[0]) >= 6 and len(c0_parts[0]) <= 10) and not (current_member_info and c0_parts[0].startswith(current_member_info.get("Member #", "###").split()[0]) and len(c0_parts) == 1) : claim_num_candidate = c0_parts[0]
                    source_claim_details["Claim#"] = claim_num_candidate
                    current_cell_idx += 1
                    
                    if len(cells) > current_cell_idx and cells[current_cell_idx].strip().isdigit() and len(cells[current_cell_idx].strip()) == 6: source_claim_details["Line/Ver#"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    if len(cells) > current_cell_idx and re.match(DATE_PATTERN_RE, cells[current_cell_idx].strip()): source_claim_details["Received Date"] = cells[current_cell_idx].strip()
                    current_cell_idx += 1
                    
                    from_cand_cell_val = cells[current_cell_idx].strip() if len(cells) > current_cell_idx else ""
                    to_cand_cell_val = cells[current_cell_idx+1].strip() if len(cells) > current_cell_idx+1 else ""
                    from_dates_f = re.findall(DATE_PATTERN_RE, from_cand_cell_val)
                    to_dates_f = re.findall(DATE_PATTERN_RE, to_cand_cell_val)
                    processed_date_cells = 0
                    
                    if len(from_dates_f) == 1 and len(to_dates_f) == 1:
                        source_claim_details["From"] = from_dates_f[0]; source_claim_details["Service Period/Date To"] = to_dates_f[0]; processed_date_cells = 2
                    elif ("MEDI-CAL" in from_cand_cell_val.upper() or lob_candidate == "Medi-Cal") and from_dates_f and len(to_dates_f) == 1 :
                        source_claim_details["From"] = from_dates_f[0]; source_claim_details["Service Period/Date To"] = to_dates_f[0]; processed_date_cells = 2
                    elif not from_dates_f and (from_cand_cell_val == "" or "MEDI-CAL" in from_cand_cell_val.upper() or lob_candidate == "Medi-Cal") and len(to_dates_f) == 2:
                        source_claim_details["From"] = to_dates_f[0]; source_claim_details["Service Period/Date To"] = to_dates_f[1]; processed_date_cells = 2
                    elif len(from_dates_f) == 2: 
                        source_claim_details["From"] = from_dates_f[0]; source_claim_details["Service Period/Date To"] = from_dates_f[1]; processed_date_cells = 1
                    elif len(from_dates_f) == 1: 
                         source_claim_details["From"] = from_dates_f[0]
                         if len(to_dates_f) == 1 and from_cand_cell_val.strip() != to_cand_cell_val.strip() : 
                            source_claim_details["Service Period/Date To"] = to_dates_f[0]; processed_date_cells = 2
                         else: 
                            source_claim_details["Service Period/Date To"] = from_dates_f[0]; processed_date_cells = 1
                    elif len(to_dates_f) == 1 : 
                        source_claim_details["From"] = from_cand_cell_val; source_claim_details["Service Period/Date To"] = to_dates_f[0]; processed_date_cells = 2
                    else: 
                        if from_cand_cell_val: source_claim_details["From"] = from_cand_cell_val
                        if to_cand_cell_val: source_claim_details["Service Period/Date To"] = to_cand_cell_val
                        if from_cand_cell_val and to_cand_cell_val: processed_date_cells = 2
                        elif from_cand_cell_val or to_cand_cell_val: processed_date_cells=1
                        else: processed_date_cells = 0
                    current_cell_idx += processed_date_cells

                    idx_proc_expected = current_cell_idx
                    idx_mod_expected = current_cell_idx + 1
                    idx_qty_expected = current_cell_idx + 2
                    idx_financial_starts_std = current_cell_idx + 3

                    proc_cand_current = cells[idx_proc_expected].strip() if idx_proc_expected < len(cells) else ""
                    proc_cand_next = cells[idx_mod_expected].strip() if idx_mod_expected < len(cells) else ""
                    
                    is_curr_proc_empty_or_invalid = (not proc_cand_current or not re.match(proc_regex, proc_cand_current))
                    is_next_proc_valid = re.match(proc_regex, proc_cand_next) is not None

                    actual_proc_val, actual_mod_val, actual_qty_val = "", "", ""

                    if is_curr_proc_empty_or_invalid and is_next_proc_valid:
                        actual_proc_val = proc_cand_next
                        if idx_qty_expected < len(cells):
                            mod_c = cells[idx_qty_expected].strip()
                            if re.match(mod_regex, mod_c): actual_mod_val = mod_c
                        if idx_financial_starts_std < len(cells):
                            qty_c_full = cells[idx_financial_starts_std].strip()
                            qty_parts = qty_c_full.split()
                            if qty_parts:
                                num_part = qty_parts[-1]
                                if qty_check(num_part): actual_qty_val = num_part
                        current_cell_idx = idx_financial_starts_std + 1
                    else:
                        if re.match(proc_regex, proc_cand_current): actual_proc_val = proc_cand_current
                        if idx_mod_expected < len(cells):
                            mod_c = cells[idx_mod_expected].strip()
                            if re.match(mod_regex, mod_c): actual_mod_val = mod_c
                            elif name_to_use_for_new_member: 
                                mod_parts_orig = mod_c.split()
                                if len(mod_parts_orig) > 1:
                                    potential_mod_orig = mod_parts_orig[-1]
                                    if mod_c.startswith(name_to_use_for_new_member) and \
                                       re.match(mod_regex, potential_mod_orig) and \
                                       mod_c == f"{name_to_use_for_new_member} {potential_mod_orig}".strip():
                                       actual_mod_val = potential_mod_orig
                        if idx_qty_expected < len(cells):
                            qty_c_full = cells[idx_qty_expected].strip()
                            qty_parts = qty_c_full.split()
                            if qty_parts:
                                num_part = qty_parts[-1] 
                                if name_to_use_for_new_member and qty_c_full.startswith(name_to_use_for_new_member) and len(qty_parts)>1:
                                     if qty_check(num_part): actual_qty_val = num_part
                                elif qty_check(qty_c_full): 
                                     actual_qty_val = qty_c_full
                                elif qty_check(num_part): 
                                     actual_qty_val = num_part
                        current_cell_idx = idx_financial_starts_std
                    
                    source_claim_details["Proc"] = actual_proc_val
                    source_claim_details["Mod"] = actual_mod_val
                    source_claim_details["Qty"] = actual_qty_val
                    
                    idx_in_source_headers_for_amt_billed = next((idx_sh for idx_sh, sh_name in enumerate(current_source_claim_headers) if sh_name == "Amount Billed"), -1)
                    if idx_in_source_headers_for_amt_billed != -1:
                        for i_sh_offset, source_header_name in enumerate(current_source_claim_headers[idx_in_source_headers_for_amt_billed:]):
                            cell_idx_for_this_sh_data = current_cell_idx + i_sh_offset
                            if cell_idx_for_this_sh_data < len(cells):
                                value_to_assign = cells[cell_idx_for_this_sh_data].strip()
                                if source_header_name in NUMERIC_FINANCIAL_HEADERS and (provider_name_identifier in value_to_assign or (name_to_use_for_new_member and name_to_use_for_new_member in value_to_assign)) :
                                    temp_val = value_to_assign.replace(provider_name_identifier, "").replace(name_to_use_for_new_member if name_to_use_for_new_member else "###","").strip()
                                    if temp_val.replace('.', '', 1).replace('-', '', 1).isdigit() or not temp_val : value_to_assign = temp_val
                                source_claim_details[source_header_name] = value_to_assign
                else: 
                    def get_next_cell_val(idx, cells_list):
                        if idx < len(cells_list): return cells_list[idx].strip(), idx + 1
                        return "", idx + 1

                    source_claim_details["Claim#"], cell_idx_iter = get_next_cell_val(cell_idx_iter, cells)
                    source_claim_details["Line/Ver#"], cell_idx_iter = get_next_cell_val(cell_idx_iter, cells)
                    source_claim_details["Received Date"], cell_idx_iter = get_next_cell_val(cell_idx_iter, cells)
                    
                    from_cell_val, temp_iter_date = get_next_cell_val(cell_idx_iter, cells)
                    to_cell_val, _ = get_next_cell_val(temp_iter_date, cells) 
                    from_cell_dates = re.findall(DATE_PATTERN_RE, from_cell_val)
                    to_cell_dates = re.findall(DATE_PATTERN_RE, to_cell_val)
                    source_claim_details["From"], source_claim_details["Service Period/Date To"] = "", ""

                    if len(from_cell_dates) == 1 and len(to_cell_dates) == 1:
                        source_claim_details["From"], source_claim_details["Service Period/Date To"] = from_cell_dates[0], to_cell_dates[0]; cell_idx_iter = temp_iter_date + 1
                    elif not from_cell_val and len(to_cell_dates) == 2:
                        source_claim_details["From"], source_claim_details["Service Period/Date To"] = to_cell_dates[0], to_cell_dates[1]; cell_idx_iter = temp_iter_date + 1
                    elif len(from_cell_dates) == 2:
                        source_claim_details["From"], source_claim_details["Service Period/Date To"] = from_cell_dates[0], from_cell_dates[1]; cell_idx_iter = temp_iter_date
                    elif len(from_cell_dates) == 1: 
                        source_claim_details["From"] = from_cell_dates[0]
                        if len(to_cell_dates) == 1 and from_cell_val.strip() != to_cell_val.strip(): 
                            source_claim_details["Service Period/Date To"] = to_cell_dates[0]; cell_idx_iter = temp_iter_date + 1
                        else: 
                            source_claim_details["Service Period/Date To"] = from_cell_dates[0]; cell_idx_iter = temp_iter_date
                    elif len(to_cell_dates) == 1 : 
                        source_claim_details["From"] = from_cell_val; source_claim_details["Service Period/Date To"] = to_cell_dates[0]; cell_idx_iter = temp_iter_date + 1
                    else: 
                        source_claim_details["From"] = from_cell_val; cell_idx_iter = temp_iter_date
                        source_claim_details["Service Period/Date To"], cell_idx_iter = get_next_cell_val(cell_idx_iter, cells)
                    
                    idx_proc_expected = cell_idx_iter
                    idx_mod_expected = cell_idx_iter + 1
                    idx_qty_expected = cell_idx_iter + 2
                    idx_financial_starts_std = cell_idx_iter + 3

                    proc_cand_current = cells[idx_proc_expected].strip() if idx_proc_expected < len(cells) else ""
                    proc_cand_next = cells[idx_mod_expected].strip() if idx_mod_expected < len(cells) else ""

                    is_curr_proc_empty_or_invalid = (not proc_cand_current or not re.match(proc_regex, proc_cand_current))
                    is_next_proc_valid = re.match(proc_regex, proc_cand_next) is not None
                    
                    actual_proc_val, actual_mod_val, actual_qty_val = "", "", ""

                    if is_curr_proc_empty_or_invalid and is_next_proc_valid:
                        actual_proc_val = proc_cand_next
                        if idx_qty_expected < len(cells):
                            mod_c = cells[idx_qty_expected].strip()
                            if re.match(mod_regex, mod_c): actual_mod_val = mod_c
                        if idx_financial_starts_std < len(cells):
                            qty_c = cells[idx_financial_starts_std].strip()
                            if qty_check(qty_c): actual_qty_val = qty_c
                        cell_idx_iter = idx_financial_starts_std + 1 
                    else:
                        if re.match(proc_regex, proc_cand_current): actual_proc_val = proc_cand_current
                        if idx_mod_expected < len(cells):
                            mod_c = cells[idx_mod_expected].strip()
                            if re.match(mod_regex, mod_c): actual_mod_val = mod_c
                        if idx_qty_expected < len(cells):
                            qty_c = cells[idx_qty_expected].strip()
                            if qty_check(qty_c): actual_qty_val = qty_c
                        cell_idx_iter = idx_financial_starts_std
                    
                    source_claim_details["Proc"] = actual_proc_val
                    source_claim_details["Mod"] = actual_mod_val
                    source_claim_details["Qty"] = actual_qty_val

                    start_idx_financial = current_source_claim_headers.index("Amount Billed") if "Amount Billed" in current_source_claim_headers else -1
                    if start_idx_financial != -1:
                        remaining_headers = [h for h in current_source_claim_headers if h not in ["Claim#", "Line/Ver#", "Received Date", "From", "Service Period/Date To", "Proc", "Mod", "Qty"]]
                        current_header_idx = 0
                        while cell_idx_iter < len(cells) and current_header_idx < len(remaining_headers):
                            header_name = remaining_headers[current_header_idx]
                            value_to_assign = cells[cell_idx_iter].strip()
                            if header_name in NUMERIC_FINANCIAL_HEADERS and provider_name_identifier in value_to_assign:
                                temp_val = value_to_assign.replace(provider_name_identifier, "").strip()
                                if temp_val.replace('.', '', 1).replace('-', '', 1).isdigit() or not temp_val: value_to_assign = temp_val
                            source_claim_details[header_name] = value_to_assign
                            cell_idx_iter +=1
                            current_header_idx +=1
                    
                    for target_h in current_source_claim_headers:
                        if target_h not in source_claim_details: source_claim_details[target_h] = ""

                final_claim_output = {hdr: "" for hdr in TARGET_CLAIM_HEADERS} 
                final_claim_output["Claim #"] = source_claim_details.get("Claim#", "")
                final_claim_output["Line/Ver#"] = source_claim_details.get("Line/Ver#", "")
                final_claim_output["Received Date"] = source_claim_details.get("Received Date", "")
                final_claim_output["Service From"] = source_claim_details.get("From", "")
                final_claim_output["Service To"] = source_claim_details.get("Service Period/Date To", "")
                final_claim_output["Proc"] = source_claim_details.get("Proc", "")
                final_claim_output["Mod"] = source_claim_details.get("Mod", "")
                final_claim_output["Qty"] = source_claim_details.get("Qty", "")
                final_claim_output["Amount Billed"] = source_claim_details.get("Amount Billed", "")
                final_claim_output["Amount Allowed"] = source_claim_details.get("Amount Allowed", "")
                final_claim_output["Not Covered"] = source_claim_details.get("Not Covered", "")
                final_claim_output["Copay/Coins"] = source_claim_details.get("Copay/Coins", "")
                final_claim_output["Deduct Amount"] = source_claim_details.get("Deduct Amount", "")
                final_claim_output["Withhold Amount"] = source_claim_details.get("Withhold Amount", "")
                final_claim_output["Net Paid"] = source_claim_details.get("Net Paid", "")
                final_claim_output["Adjust"] = source_claim_details.get("Adjust", "")
                # Patient Acct. # is no longer added here

                original_interest_val = source_claim_details.get("Interest", "")
                final_claim_output["Interest"] = original_interest_val

                if table_type == 1:
                    st_val, reason_val = source_claim_details.get('S T', ''), source_claim_details.get('Reason', '')
                    st_parts = st_val.split(maxsplit=1)
                    if len(st_parts) > 1 and (not reason_val or reason_val == st_parts[1] or reason_val.startswith(st_parts[1])):
                        final_claim_output['ST'], final_claim_output['Reason'] = st_parts[0], st_parts[1]
                    elif len(st_parts) == 1 and not reason_val :
                        final_claim_output['ST'] = st_parts[0]; final_claim_output['Reason'] = ""
                    else:
                        final_claim_output['ST'] = st_val; final_claim_output['Reason'] = reason_val
                else: 
                    st_reason_val = source_claim_details.get('S T Reason', '')
                    parts = st_reason_val.split(maxsplit=1)
                    final_claim_output['ST'] = parts[0] if parts else st_reason_val
                    if len(parts) > 1:
                        final_claim_output['Reason'] = parts[1]
                    elif original_interest_val and not final_claim_output.get('Reason') and \
                         not original_interest_val.replace('.','',1).replace('-', '', 1).isdigit() and \
                         original_interest_val.strip() and original_interest_val != "0.00":
                        final_claim_output['Reason'], final_claim_output['Interest'] = original_interest_val, ""
                    else:
                        final_claim_output['Reason'] = ""
                
                is_truly_data_deficient = True
                # A claim is only valid if it has a claim number AND it's not the provider ID.
                # Or, if it doesn't have a claim number but has other significant data.
                claim_num_val = final_claim_output.get("Claim #", "").strip()
                if claim_num_val and claim_num_val != "823779224": 
                    key_data_fields = ["Line/Ver#", "Received Date", "Service From", "Proc", "Amount Billed", "Net Paid"]
                    if any(final_claim_output.get(k,"").strip() for k in key_data_fields):
                        is_truly_data_deficient = False
                elif not claim_num_val: # No claim number
                    # Still could be valid if other critical parts are there (e.g. for Anderson, Michael example)
                    if final_claim_output.get("Line/Ver#","").strip() and \
                       final_claim_output.get("Received Date","").strip() and \
                       final_claim_output.get("Proc","").strip():
                       is_truly_data_deficient = False


                if not is_truly_data_deficient:
                    current_member_info["claims"].append(final_claim_output)

        except Exception as e:
            print(f"CRITICAL ERROR processing line {line_idx + 1} in table block: '{line_raw.strip()}'")
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

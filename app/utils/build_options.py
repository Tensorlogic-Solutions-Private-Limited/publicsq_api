def build_options(question_obj, include_answers: bool = False):
    """
    Builds a list of options for the given question, including is_correct flag if admin.
    """
    options = []
    texts = [
        question_obj.qmt_option1,
        question_obj.qmt_option2,
        question_obj.qmt_option3,
        question_obj.qmt_option4
    ]
    correct = question_obj.qmt_correct_answer
    option_dict = {1: 'A', 2: 'B', 3: 'C', 4: 'D'}

    # Normalize "option A" -> "A"
    if isinstance(correct, str):
        # Get last word & upper-case
        correct = correct.strip().split()[-1].upper()  

    for i, text in enumerate(texts, start=1):
        opt_id = option_dict[i]
        opt = {
            "id": opt_id,
            "text": text
        }
        if include_answers:
            opt["is_correct"] = opt_id == correct
        options.append(opt)

    return options
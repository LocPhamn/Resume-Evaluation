import spacy
from streamlit_tags import st_tags
import wordninja

spacy.load('en_core_web_sm')
import base64
from sentence_transformers import SentenceTransformer, util

from pprint import pprint
from pdfminer3.layout import LAParams, LTTextBox
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager
from pdfminer3.pdfinterp import PDFPageInterpreter
from pdfminer3.converter import TextConverter

import io
import re
import streamlit as st



def pdf_reader(file):
    resource_manager = PDFResourceManager() # cung cấp tai nguyên giúp định vị lấy thông tin chính xác
    fake_file_handle = io.StringIO() # mở ra file lưu trữ ảo tránh ghi file tạm
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams()) # sử dụng tài nguyên và file ảo chuyển đổi nd -> text
    page_interpreter = PDFPageInterpreter(resource_manager, converter) # lật trang dùng thêm tài nguyên và chuyển đổii
    with open(file, 'rb') as fh: # Mở file ở chế độ nhị phân ('rb') vì PDF là định dạng binary, không thể mở như text bình thường
        for page in PDFPage.get_pages(fh,
                                      caching=True,
                                      check_extractable=True):
            page_interpreter.process_page(page)
            # print(page)
        text = fake_file_handle.getvalue()

    # giải phóng bộ nhớ và đóng ram ảo
    converter.close()
    fake_file_handle.close()
    return text

def extract_name(text):
    # Tìm dòng đầu tiên có 2-4 từ in hoa
    match = re.search(r'^[A-Z][A-Z\s]{2,}$', text, re.MULTILINE)
    if match:
        return match.group(0).strip()
    return None

def extract_email(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None

def extract_numbers(text):
    match = re.search(r'(\+84|0)?[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3,4}', text)
    return match.group(0) if match else None


def extract_address(text):
    match = re.search(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*),\s*(Vietnam|Việt Nam|Viet Nam)\b', text)
    return match.group(0) if match else None

def extract_profile(text):
    match = re.search(
        r'PROFILE\s*\n(.*?)(?=\n[A-Z][A-Z\s]{2,}|$)',  # Bắt nội dung cho đến khi gặp tiêu đề tiếp theo viết hoa
        text,
        re.DOTALL
    )
    if match:
        return match.group(1).strip()
    return None

def extract_experience(text):
    match = re.search(
        r'EXPERIENCE\s*\n(.*?)(?=\n[A-Z][A-Z\s]{2,}|$)',
        text,
        re.DOTALL
    )

    if not match:
        return []

    raw_experience = match.group(1).strip()

    # Chia dòng
    lines = raw_experience.splitlines()

    bullet_points = []
    current_line = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Nếu là dòng bắt đầu bằng bullet (• - *)
        if re.match(r'^[•*-]', line):
            if current_line:
                bullet_points.append(fix_spacing_line(current_line))
            current_line = re.sub(r'^[•*-]\s*', '', line)
        else:
            # Dòng tiếp theo của bullet → nối vào dòng trước
            current_line += " " + line

    if current_line:
        bullet_points.append(fix_spacing_line(current_line))

    return bullet_points

def extract_skill_block(text, header_start,header_end=None):
    # Lấy đoạn từ HEADER đến hết (không dừng lại ở dòng in hoa tiếp theo nữa)
    header_start = re.escape(header_start)
    if header_end:
        header_end = re.escape(header_end)
        # Pattern giữa 2 header
        pattern = rf"{header_start}\s*\n(.*?)(?=\n{header_end}\s*\n)"
    else:
        # Nếu không có header2 → trích từ header1 đến hết
        pattern = rf"{header_start}\s*\n([\s\S]*)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_skills_from_block(block_text):
    # Lấy tất cả từ/tên kỹ năng, bao gồm cả chữ có dấu chấm, chữ hoa thường, v.v.
    tokens = re.findall(r'\b[\w\.-]+\b', block_text)

    # Nếu muốn bỏ những từ không cần thiết thì lọc ở đây
    unwanted = set()
    skills = [token for token in tokens if token not in unwanted]
    return skills


def clean_resume(text):
    lines = text.splitlines()
    non_blank_lines = [line.strip() for line in lines if line.strip()]
    text = '\n'.join(non_blank_lines)


    # Chuẩn hóa các tiêu đề viết hoa về dạng dễ xử lý
    text = re.sub(r'\b(PROFILE|EXPERIENCE|TECHNICAL SKILL|OTHERS SKILL|EDUCATION|PROJECTS|CERTIFICATES|CONTACT)\b',
                  lambda m: m.group(1).upper(), text, flags=re.IGNORECASE)

    return text.strip()

def fix_spacing_line(line):
    # Chỉ sửa những dòng có ít khoảng trắng
    if len(re.findall(r'\s', line)) < 2 and len(line) > 20:
        return ' '.join(wordninja.split(line))
    return line
def extract_information(save_pdf_path):
    text = pdf_reader(save_pdf_path)
    # print(text)
    cleaned_resume = clean_resume(text)

    # print(cleaned_resume)
    name = extract_name(cleaned_resume)
    email = extract_email(cleaned_resume)
    numbers = extract_numbers(cleaned_resume)
    address = extract_address(cleaned_resume)
    profile = extract_profile(cleaned_resume)
    experience = extract_experience(cleaned_resume)
    block_tech_skill = extract_skill_block(cleaned_resume,"TECHNICAL SKILL","OTHERS SKILL")
    tech_skill = extract_skills_from_block(block_tech_skill)
    block_other_skill = extract_skill_block(cleaned_resume, "OTHERS SKILL")
    other_skill = extract_skills_from_block(block_other_skill)
    resume = {
        "name": name,
        "email": email,
        "contact": numbers,
        "address": address,
        "profile": profile,
        "experience": experience,
        "skills": tech_skill + other_skill
    }
    return resume

def avg_cosine_score(cv_items, jd_items):
    if not cv_items or not jd_items:
        return 0.0
    cv_embeddings = model.encode(cv_items, convert_to_tensor=True)
    jd_embeddings = model.encode(jd_items, convert_to_tensor=True)
    scores = util.cos_sim(cv_embeddings, jd_embeddings)
    best_match = [float(scores[:, i].max()) for i in range(scores.shape[1])]
    return round(sum(best_match) / len(best_match), 2)

def show_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    # pdf_display = f'<embed src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf">'
    pdf_display = F'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)


def run(model):
    # Title of the app
    st.title("Validate Resume")
    pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
    if pdf_file is not None:

        # save_pdf_path = "your pdf path store"
        save_pdf_path = r"D:\Python plus\NLP_AI\src\nlp\sample\{}".format(pdf_file.name)
        show_pdf(save_pdf_path)
        resume = extract_information(save_pdf_path)

        if resume:
            ## Get the whole resume data
            resume_text = pdf_reader(save_pdf_path)

            st.header("**Resume Analysis**")
            st.success("Hello " + resume['name'])
            st.subheader("**Your Basic info**")
            try:
                st.text('Name: ' + resume['name'])
                st.text('Email: ' + resume['email'])
                st.text('Contact: ' + resume['contact'])
                st.text('Address: ' + resume['address'])
                st.text('Profile' + resume['profile'])

                # st.text('Resume pages: ' + str(resume['no_of_pages']))
            except:
                pass

            # Job skills
            ds_skills = ['tensorflow', 'keras', 'pytorch', 'machine learning', 'deep Learning', 'flask',
                         'streamlit']
            web_skills = ['react native', 'asp.net', 'javascript', 'nextjs', 'django', 'nodejs', 'reactjs', 'php',
                          'laravel', 'magento', 'wordpress',
                          'javascript', 'angularjs', 'c#']
            android_skills = ['android', 'android development', 'flutter', 'kotlin', 'xml', 'kivy']
            ios_skill = ['ios', 'ios development', 'swift', 'cocoa', 'cocoa touch', 'xcode']

            uiux_skills = ['ux', 'adobe xd', 'figma', 'zeplin', 'balsamiq', 'ui', 'prototyping', 'wireframes',
                           'storyframes', 'adobe photoshop', 'photoshop', 'editing', 'adobe illustrator',
                           'illustrator', 'adobe after effects', 'after effects', 'adobe premier pro',
                           'premier pro', 'adobe indesign', 'indesign', 'wireframe', 'solid', 'grasp',
                           'user research', 'user experience']

            # job_experience
            ds_experience = [
                "Built several small-scale machine learning models using TensorFlow, Keras, and PyTorch as part of personal projects and online courses.",
                "Applied deep learning techniques to image classification problems.",
                "Deployed a model using Streamlit and Flask for demonstration."
            ]

            web_experience = [
                "Worked as an ASP.NET MVC Intern Developer at Hanoi University of Industry from Sep 2024 to Dec 2024.",
                "Collaborated with cross-functional teams in an Agile environment to deliver web-based solutions.",
                "Developed backend services using ASP.NET Core by building RESTful APIs and implementing business logic.",
                "Integrated frontend interfaces with backend APIs to enable dynamic user interactions.",
                "Designed and optimized SQL Server databases to ensure efficient data storage and query performance."
            ]

            android_experience = [
                "Built a basic Android application using Kotlin and XML layouts as part of a semester project.",
                "Experimented with cross-platform app development using Flutter for a personal task manager app.",
                "Familiar with Android Studio and mobile app UI design fundamentals."
            ]

            ios_experience = [
                "Completed an online course on iOS development using Swift and Xcode.",
                "Created a simple to-do list app with custom UI elements and integrated local storage using Core Data.",
                "Practiced interface design using Interface Builder and storyboard-based navigation."
            ]

            uiux_experience = [
                "Designed wireframes and interactive prototypes using Figma and Adobe XD for mock startup apps.",
                "Learned user research and persona development through design thinking workshops.",
                "Created UI assets and visual design mockups using Adobe Illustrator and Photoshop.",
                "Familiar with the design-to-development handoff process using Zeplin."
            ]

            ## visualize skill
            for i in resume['skills']:
                ## Data science recommendation
                if i.lower() in web_skills:
                    reco_field = 'Web developer'
                    st.success("** Our analysis says you are looking for Front End Jobs.**")
                    recommended_skills = resume['skills']
                    recommended_keywords = st_tags(label='### Your skills.',
                                                   text='',
                                                   value=recommended_skills, key='2')

                    break
                elif i in ds_skills:
                    reco_field = 'Data Scientist / ML Engineer'
                    st.success("**🤖 Our analysis says you are looking for a Data Science or Machine Learning job.**")
                    recommended_skills = resume['skills']
                    recommended_keywords = st_tags(label='### Your skills.', text='', value=recommended_skills,
                                                   key='ds')
                    job_skills = ds_skills
                    job_experience = ds_experience
                    break

                elif i in android_skills:
                    reco_field = 'Android Developer'
                    st.success("**📱 Our analysis says you are looking for an Android Development job.**")
                    recommended_skills = resume['skills']
                    recommended_keywords = st_tags(label='### Your skills.', text='', value=recommended_skills,
                                                   key='android')
                    job_skills = android_skills
                    job_experience = android_experience
                    break

                elif i in ios_skill:
                    reco_field = 'iOS Developer'
                    st.success("**🍏 Our analysis says you are looking for an iOS Development job.**")
                    recommended_skills = resume['skills']
                    recommended_keywords = st_tags(label='### Your skills.', text='', value=recommended_skills,
                                                   key='ios')
                    job_skills = ios_skill
                    job_experience = ios_experience
                    break

                elif i in uiux_skills:
                    reco_field = 'UI/UX Designer'
                    st.success("**🎨 Our analysis says you are looking for a UI/UX Designer position.**")
                    recommended_skills = resume['skills']
                    recommended_keywords = st_tags(label='### Your skills.', text='', value=recommended_skills,
                                                   key='uiux')
                    job_skills = uiux_skills
                    job_experience = uiux_experience
                    break

            # Experience
            st.subheader("**Experience**")
            if(resume['experience']):
                for i in resume['experience']:
                    st.text(i)
            else:
                st.text("Not have any experience")

            # Resume evaluate
            st.subheader("Your resume point")
            skill_score = avg_cosine_score(resume['skills'], web_skills)
            exp_score = avg_cosine_score(resume['experience'], web_experience)
            total_score = round(0.4 * skill_score + 0.6 * exp_score, 2)

            st.subheader(total_score)
            if total_score > 0.75:
                st.success("✅ High match (Tuyệt vời cho vị trí này!)")
            elif total_score > 0.5:
                st.info("🤝 Medium match (Cần cân nhắc)")
            else:
                st.error("❌ Low match (Chưa phù hợp)")


if __name__ == '__main__':
    model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    run(model)



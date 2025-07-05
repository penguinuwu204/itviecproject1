ITViec Explorer

🔍 ITViec Explorer** là ứng dụng web được xây dựng bằng Streamlit, phục vụ cho việc phân tích đánh giá công ty IT thu thập từ ITViec.com.  

## 🚀 Tính năng chính

1. **Content-Based Similarity**  
   - So sánh **Overview** công ty và **Reviews** qua các phương pháp:
     - TF-IDF (Scikit-Learn)
     - Gensim-TFIDF
     - Word2Vec (IDF-weighted)
     - FastText (IDF-weighted)
   - So sánh **Numeric Ratings** (điểm số đánh giá).

2. **Recommendation Classification**  
   - Dự đoán nhãn **Recommend? (Yes/No)** cho mỗi review:
     - Scikit-Learn: Logistic Regression, Random Forest, SVM, XGBoost
     - PySpark MLlib: Logistic Regression, Decision Tree, Random Forest
   - Giao diện **Interactive**: nhập partial tên công ty, xem tỉ lệ recommend và xác suất từng review.

3. **EDA & WordCloud**  
   - Trực quan hóa dữ liệu công ty, điểm số đánh giá và reviews với biểu đồ và WordCloud.

## 📦 Cấu trúc thư mục
.
├── app.py # Main Streamlit app
├── requirements.txt # Các package Python cần cài
└── README.md # ← File này


## ⚙️ Hướng dẫn cài đặt & chạy

1. Tạo môi trường ảo và cài dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
Chạy ứng dụng:

streamlit run app.py
Mở trình duyệt truy cập địa chỉ hiển thị (mặc định http://localhost:8501).

📋 requirements.txt (ví dụ)
streamlit>=1.10
pandas
numpy
scipy
scikit-learn
imbalanced-learn
xgboost
gensim
deep-translator
spacy
pyspark
wordcloud
regex
Lưu ý: nếu dùng spaCy, bạn có thể cần tải mô hình tiếng Anh:
python -m spacy download en_core_web_sm

👥 Nhóm thực hiện:
Nguyễn Lư Bảo Khang (nbaokhang12@gmail.com)
Phạm Đức Huy (DucHuyUFM@gmail.com)

GVHD: Ms. Khuất Thùy Phương
Đồ án Tốt nghiệp – Data Science & Machine Learning, Trường Đại học KHTN, TTTH

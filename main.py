import sys
import io
import os
import re
import tempfile
from flask import Flask, request, jsonify, send_file
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()  

app = Flask(__name__)


client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

def analyze_sentiment(text):
    prompt = f"""Analyze the sentiment of the following text and provide scores for positive, negative, and neutral sentiments. 
    The scores should sum to 1 and be formatted as follows:
    Positive: [score]
    Negative: [score]
    Neutral: [score]
    
    Text: {text}"""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="mixtral-8x7b-32768",
            temperature=0.5,
        )
        
        response = chat_completion.choices[0].message.content
        print(f"API Response: {response}")  # Log the API response
        
        
        pattern = r'(Positive|Negative|Neutral): (0(?:\.\d+)?|\.\d+|1(?:\.0+)?)'
        matches = re.findall(pattern, response)
        
        scores = {sentiment.lower(): float(score) for sentiment, score in matches}
        
        
        for sentiment in ['positive', 'negative', 'neutral']:
            if sentiment not in scores:
                scores[sentiment] = 0.0
        
        
        score_sum = sum(scores.values())
        if abs(score_sum - 1) < 0.01:
            return scores
        else:
            print(f"Score sum not equal to 1. Scores: {scores}, Sum: {score_sum}")
            
            normalized_scores = {k: v / score_sum for k, v in scores.items()}
            return normalized_scores
    
    except Exception as e:
        print(f"Error in sentiment analysis: {str(e)}")
        
        return {"positive": 0.33, "negative": 0.33, "neutral": 0.34}

@app.route('/analyze', methods=['POST'])
def analyze_reviews():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        try:
           
            if file.filename.endswith('.csv'):
               
                df = pd.read_csv(file, header=None, names=['review'], encoding='utf-8')
            elif file.filename.endswith('.xlsx'):
             
                df = pd.read_excel(file)
                df = df.rename(columns={df.columns[0]: 'review'})
            else:
                return jsonify({"error": "Unsupported file format"}), 400
            
           
            reviews = df['review'].tolist()
            
            
            results = []
            for review in reviews:
                sentiment = analyze_sentiment(review)
                results.append(sentiment)
                print(f"Review: {review}")
                print(f"Sentiment: {sentiment}")
            
          
            df['positive'] = [result['positive'] for result in results]
            df['negative'] = [result['negative'] for result in results]
            df['neutral'] = [result['neutral'] for result in results]
            
          
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
                df.to_csv(temp_file.name, index=False, encoding='utf-8')
            
            
            return send_file(temp_file.name, as_attachment=True, download_name='sentiment_analysis_results.csv', mimetype='text/csv')
        
        except Exception as e:
            print(f"Error in analyze_reviews: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Invalid file format"}), 400

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv', 'xlsx'}

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import google.generativeai as genai
import markdown

from seed_data_1 import get_infectious_diseases
from seed_data_2 import get_lifestyle_respiratory_diseases
from seed_data_3 import get_digestive_skin_diseases
from seed_data_4 import get_deficiency_diseases

# --- Configure Gemini AI API Key ---
# IMPORTANT: Put your Gemini API Key here inside the quotes
GEMINI_API_KEY = "YOUR_API_KEY_HERE"
# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-this-in-production') # Needed for Flask sessions/flash messages

# Configure SQLite Database
basedir = os.path.abspath(os.path.dirname(__name__))
database_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'vitality.db'))
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Redirection point if a user isn't logged in
login_manager.login_message_category = 'info'

# --- Database Models ---

# Association table for Many-to-Many relationship between Users and Articles
user_bookmarks = db.Table('user_bookmarks',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    # Relationship to bookmarked Articles
    bookmarks = db.relationship('Article', secondary=user_bookmarks, lazy='subquery',
        backref=db.backref('bookmarked_by', lazy=True))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    # The 12 Medical Sections
    definition = db.Column(db.Text, nullable=True)
    causes = db.Column(db.Text, nullable=True)
    risk_factors = db.Column(db.Text, nullable=True)
    symptoms = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    treatment = db.Column(db.Text, nullable=True)
    medicines = db.Column(db.Text, nullable=True)
    diet = db.Column(db.Text, nullable=True)
    home_remedies = db.Column(db.Text, nullable=True)
    prevention = db.Column(db.Text, nullable=True)
    recovery_time = db.Column(db.Text, nullable=True)
    when_to_see_doctor = db.Column(db.Text, nullable=True)

# Login Manager user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --- Routes ---

@app.route('/')
def home():
    """Serve the main homepage."""
    # We pass current_user to the template automatically via Flask-Login
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Basic validation
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please log in.', 'error')
            return redirect(url_for('register'))
            
        # Create new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required # Requires user to be logged in to access this route
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    """User profile dashboard displaying saved models."""
    return render_template('profile.html', user=current_user)

@app.route('/api/bookmark/<int:article_id>', methods=['POST'])
@login_required
def toggle_bookmark(article_id):
    """Toggle a bookmark for the current user."""
    article = Article.query.get_or_404(article_id)
    
    if article in current_user.bookmarks:
        current_user.bookmarks.remove(article)
        action = 'removed'
    else:
        current_user.bookmarks.append(article)
        action = 'added'
        
    db.session.commit()
    return jsonify({"status": "success", "action": action, "article_id": article_id})

@app.route('/api/search', methods=['GET'])
def search_api():
    """Handle frontend search queries using the database."""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({"results": []})
        
    # Search database for articles matching the query in title or category
    search_term = f"%{query}%"
    articles = Article.query.filter(
        db.or_(
            db.func.lower(Article.title).like(search_term),
            db.func.lower(Article.category).like(search_term)
        )
    ).all()
    
    # Check which of these are bookmarked currently if logged in
    bookmarked_ids = []
    if current_user.is_authenticated:
        bookmarked_ids = [a.id for a in current_user.bookmarks]
    
    results = [{
        "id": a.id,
        "title": a.title, 
        "category": a.category, 
        "definition": a.definition,
        "causes": a.causes,
        "risk_factors": a.risk_factors,
        "symptoms": a.symptoms,
        "diagnosis": a.diagnosis,
        "treatment": a.treatment,
        "medicines": a.medicines,
        "diet": a.diet,
        "home_remedies": a.home_remedies,
        "prevention": a.prevention,
        "recovery_time": a.recovery_time,
        "when_to_see_doctor": a.when_to_see_doctor,
        "is_bookmarked": a.id in bookmarked_ids
    } for a in articles]
    return jsonify({"results": results})

# --- Database Initialization Helper ---

def init_db():
    """Create the database tables and prepopulate some initial articles."""
    db.create_all()
    # Prepopulate demo data if empty
    if Article.query.count() == 0:
        demo_articles = [
            Article(
                title="Fever (High Body Temperature)", 
                category="General Medicine",
                definition="A temporary increase in your body temperature, often due to an illness or infection. Normal body temperature is around 98.6°F (37°C), though a fever is usually defined as a temperature of 100.4°F (38°C) or higher.",
                causes="<ul><li>Viral or bacterial infections (flu, cold, strep throat)</li><li>Heat exhaustion</li><li>Inflammatory conditions (rheumatoid arthritis)</li><li>Certain medications</li><li>Immunizations (vaccines)</li></ul>",
                risk_factors="Children and infants are highly susceptible as their immune systems develop. Elderly individuals and those with compromised immune systems or chronic diseases are also at higher risk.",
                symptoms="**Early/Mild:**<br><ul><li>Sweating and chills</li><li>Headache</li><li>Muscle aches</li><li>Loss of appetite</li></ul>**Severe:**<br><ul><li>Confusion</li><li>Extreme irritability</li><li>Seizures (especially in young children)</li></ul>",
                diagnosis="Diagnosis is primarily made using a medical thermometer. Doctors will also conduct a physical exam and may order blood tests, urine tests, or chest X-rays to determine the underlying cause of the fever.",
                treatment="Treatment focuses on the underlying cause. For viral infections, treatment is supportive (rest, fluids). Bacterial infections require antibiotics. Over-the-counter fever reducers are used for comfort.",
                medicines="<ul><li>**Acetaminophen (Tylenol):** Reduces fever and pain.</li><li>**Ibuprofen (Advil, Motrin):** Reduces fever, pain, and inflammation.</li><li>**Antibiotics:** (Only if prescribed for a bacterial infection).</li></ul>",
                diet="**To Eat:** Soups, broths, water-rich foods (watermelon, cucumber), easily digestible foods (toast, crackers), herbal teas.<br>**To Avoid:** Alcohol, caffeine, heavy greasy foods, highly sugary items.",
                home_remedies="<ul><li>Rest heavily.</li><li>Stay hydrated with water or electrolyte drinks.</li><li>Apply a cool, damp cloth to the forehead.</li><li>Take a lukewarm (not cold) bath.</li></ul>",
                prevention="Wash hands frequently, avoid close contact with sick individuals, get vaccinated (like the annual flu shot), and maintain general hygiene to avoid infections that cause fevers.",
                recovery_time="For simple viral infections, a fever usually subsides within 3 to 5 days. For more complex infections, recovery depends entirely on the effectiveness of the treatment.",
                when_to_see_doctor="Seek immediate attention if: The fever is over 103°F (39.4°C), lasts more than 3 days, or is accompanied by a severe headache, stiff neck, shortness of breath, or a rash."
            ),
            Article(
                title="Common Cold", 
                category="General Medicine",
                definition="A viral infection of your upper respiratory tract (nose and throat). It is generally harmless, though it might not feel like it.",
                causes="Rhinoviruses are the most common cause, though many other viruses can cause a cold. Viruses enter the body through the mouth, eyes, or nose, often transmitted via airborne droplets when someone sick coughs or sneezes.",
                risk_factors="Children are most at risk, especially those in daycare. Times of year (Fall and Winter) and weakened immune systems (due to stress or lack of sleep) increase susceptibility.",
                symptoms="**Early:**<br><ul><li>Runny or stuffy nose</li><li>Sore throat</li><li>Sneezing</li></ul>**Peak:**<br><ul><li>Mild body aches</li><li>Low-grade fever</li><li>Mild headache</li><li>Cough</li></ul>",
                diagnosis="Doctors diagnose a cold based almost entirely on your signs and symptoms. Swab tests are occasionally used to rule out Flu or COVID-19 if symptoms are severe.",
                treatment="There is no cure for the common cold. Treatment is directed at relieving symptoms. Antibiotics are completely ineffective against viruses.",
                medicines="<ul><li>**Decongestants (Sudafed):** For stuffy noses.</li><li>**Pain Relievers (Acetaminophen, Ibuprofen):** For fever and aches.</li><li>**Cough Syrups/Drops:** To soothe throat irritation.</li></ul>",
                diet="**To Eat:** Warm chicken soup (scientifically proven to reduce inflammation), warm water with lemon and honey, ginger tea.<br>**To Avoid:** Dairy products (can thicken mucus in some individuals), caffeine (dehydrating).",
                home_remedies="<ul><li>Use a cool-mist humidifier to add moisture to the air.</li><li>Gargle saltwater (1/4 tsp salt to 8oz warm water) to soothe a sore throat.</li><li>Use saline nasal drops or sprays.</li></ul>",
                prevention="Wash your hands thoroughly and often. Disinfect frequently touched surfaces. Don't share glasses or utensils. Eat a balanced diet, exercise, and get plenty of sleep to maintain a strong immune system.",
                recovery_time="Most people recover fully within 7 to 10 days. Symptoms might last longer in people who smoke.",
                when_to_see_doctor="See a doctor if symptoms worsen or fail to improve after 10 days, if you develop a severe sore throat, ear pain, or a fever higher than 101.3°F (38.5°C)."
            ),
            Article(
                title="Typhoid Fever", 
                category="Infectious Disease",
                definition="A life-threatening bacterial infection caused by *Salmonella* Typhi. It is typically transmitted through contaminated food or water.",
                causes="Caused by the bacterium *Salmonella enterica* serotype Typhi. It spreads through the fecal-oral route (eating/drinking contaminated items).",
                risk_factors="Traveling to or living in areas where typhoid is endemic (parts of Asia, Africa, South America), drinking untreated water, poor sanitation, and working as a clinical microbiologist handling the bacteria.",
                symptoms="**Early:**<br><ul><li>Prolonged high fever (up to 104.9°F / 40.5°C)</li><li>Headache</li><li>Weakness and fatigue</li><li>Dry cough</li></ul>**Later:**<br><ul><li>Abdominal pain and diarrhea (or constipation)</li><li>A rash of flat, rose-colored spots</li><li>Delirium or intestinal bleeding/perforation in severe cases</li></ul>",
                diagnosis="Diagnosed primarily via blood culture to detect *Salmonella* Typhi. Stool, urine, or bone marrow cultures may also be used.",
                treatment="Antibiotic therapy is the only effective treatment for typhoid fever. Supportive care with hydration and rest is also critical.",
                medicines="<ul><li>**Antibiotics:** Fluoroquinolones (like ciprofloxacin), Cephalosporins (like ceftriaxone), or Azithromycin.</li><li>**Antipyretics:** Acetaminophen for fever management.</li></ul>",
                diet="**To Eat:** High-calorie, high-protein foods that are easily digestible (boiled eggs, clear soups, plain rice, bananas, porridge). Drink boiled or bottled water and oral rehydration solutions.<br>**To Avoid:** Raw fruits/vegetables (unless peeled), spicy foods, high-fiber foods (can irritate the bowel), dairy if it worsens diarrhea.",
                home_remedies="<ul><li>Drink plenty of fluids to prevent dehydration from prolonged fever and diarrhea.</li><li>Apply cold compresses to help lower body temperature.</li><li>Complete bed rest is mandatory.</li></ul>",
                prevention="Get vaccinated before traveling to high-risk areas. Always 'boil it, cook it, peel it, or forget it'. Drink only bottled or actively boiling water. Practice strict hand hygiene after using the restroom and before eating.",
                recovery_time="With prompt antibiotic treatment, improvement usually begins within a few days, and recovery takes 1 to 2 weeks. Without treatment, it can take weeks or months, and complications can be fatal.",
                when_to_see_doctor="You must see a doctor immediately if you suspect typhoid, especially if you have an unexplained high fever and have recently traveled to an endemic area."
            ),
            Article(
                title="Malaria", 
                category="Infectious Disease",
                definition="A serious and sometimes fatal disease caused by a parasite that commonly infects a certain type of mosquito which feeds on humans. It causes severe shivering and fever.",
                causes="Caused by *Plasmodium* parasites. The parasites are transmitted to humans through the bites of infected female *Anopheles* mosquitoes.",
                risk_factors="Living in or traveling to tropical and subtropical regions (Sub-Saharan Africa, South Asia, parts of South America). Young children, pregnant women, and travelers with no previous immunity are at the highest risk.",
                symptoms="**Classic \"Malaria Attack\" Cycle:**<br><ol><li>A cold stage (shivering and chills)</li><li>A hot stage (high fever, headache, vomiting)</li><li>A sweating stage (profuse sweating, return to normal temperature, extreme fatigue)</li></ol>**Other symptoms:** Muscle pain, diarrhea, anemia, jaundice.",
                diagnosis="Diagnosed using a blood test (thick and thin blood smears examined under a microscope) or via Rapid Diagnostic Tests (RDTs) which detect specific malaria antigens in the blood.",
                treatment="Malaria is a medical emergency and must be treated with prescription antimalarial drugs to kill the parasite.",
                medicines="<ul><li>**Artemisinin-based combination therapies (ACTs):** The primary treatment (e.g., Artemether-lumefantrine).</li><li>**Chloroquine:** Used for sensitive strains.</li><li>**Atovaquone-proguanil (Malarone):** Often used for prevention and treatment.</li></ul>",
                diet="**To Eat:** Foods rich in iron (spinach, red meat, beans) to combat anemia caused by parasite destruction of red blood cells. Easily digestible carbohydrates, citrus fruits.<br>**To Avoid:** Heavy, greasy, or highly spicy foods during the acute phase of nausea.",
                home_remedies="<ul><li>Stay hydrated with electrolyte solutions.</li><li>Rest extensively.</li><li>*Note:* Home remedies cannot cure malaria; they only offer supportive comfort while medications kill the parasite.</li></ul>",
                prevention="Take prophylactic antimalarial drugs before, during, and after travel to risk areas. Sleep under an insecticide-treated mosquito net. Use insect repellent containing DEET, wear long sleeves and pants, and spray rooms with insecticides.",
                recovery_time="With proper treatment, symptoms generally resolve within a few days, and complete recovery is typically achieved within 2 weeks.",
                when_to_see_doctor="Seek immediate medical attention if you experience a high fever and chills, especially if you have recently traveled to a region where malaria is present."
            ),
            Article(
                title="Type 2 Diabetes", 
                category="Endocrinology",
                definition="A chronic, lifelong condition that affects how your body metabolizes sugar (glucose). In Type 2 diabetes, the body either resists the effects of insulin or doesn't produce enough insulin to maintain normal glucose levels.",
                causes="Develops when the body becomes resistant to insulin or when the pancreas is unable to produce enough insulin. The exact reason is unknown, but genetics and environmental factors, such as being overweight and inactive, seem to be contributing factors.",
                risk_factors="Carrying excess weight, physical inactivity, having a family history of diabetes, being older than 45, having a history of gestational diabetes, and having specific conditions like polycystic ovary syndrome (PCOS).",
                symptoms="**Early:**<br><ul><li>Increased thirst and frequent urination</li><li>Increased hunger</li><li>Unintended weight loss</li><li>Fatigue</li><li>Blurred vision</li></ul>**Later:**<br><ul><li>Slow-healing sores</li><li>Frequent infections</li><li>Numbness or tingling in the hands or feet</li></ul>",
                diagnosis="Diagnosed using blood tests. The Glycated hemoglobin (A1C) test measures average blood sugar over 2-3 months. Other tests include a random blood sugar test, fasting blood sugar test, or oral glucose tolerance test.",
                treatment="There is no cure for Type 2 diabetes. Treatment involves managing the condition through lifestyle changes, oral medications, and sometimes insulin therapy.",
                medicines="<ul><li>**Metformin:** The primary initial medication (reduces glucose production in the liver).</li><li>**Sulfonylureas:** Help your body secrete more insulin.</li><li>**DPP-4 inhibitors / SGLT2 inhibitors:** Help manage blood sugar via different bodily mechanisms.</li><li>**Insulin therapy:** Required if oral medications fail.</li></ul>",
                diet="**To Eat:** A balanced diet consisting mainly of whole grains, lean proteins (chicken, fish, tofu), healthy fats (olive oil, avocados), and non-starchy vegetables. High-fiber foods are crucial.<br>**To Avoid:** Refined carbohydrates (white bread, white rice), sugary beverages (soda, fruit juices), trans fats, and highly processed, packaged foods.",
                home_remedies="<ul><li>Engage in regular physical activity (e.g., brisk walking, cycling) for at least 150 minutes a week—exercise naturally lowers blood sugar.</li><li>Maintain a healthy weight.</li><li>Manage stress, which can spike blood sugar.</li></ul>",
                prevention="Make healthy lifestyle choices: Eat healthy foods, get active, lose excess weight, and avoid leading a sedentary lifestyle for long periods.",
                recovery_time="Type 2 diabetes is a chronic, lifelong condition. 'Recovery' is defined as successfully managing blood sugar levels to prevent complications.",
                when_to_see_doctor="See a doctor if you notice any typical symptoms, or if you already have a diagnosis and your blood sugar levels are consistently too high or too low, or if you develop new symptoms like slow-healing sores or vision changes."
            ),
            Article(
                title="Dengue Fever", 
                category="Infectious Disease",
                definition="A mosquito-borne viral infection that causes a severe flu-like illness, and sometimes a potentially lethal complication called severe dengue (dengue hemorrhagic fever).",
                causes="Caused by any one of four closely related dengue viruses. The viruses are transmitted to humans through the bites of infected *Aedes* species mosquitoes (primarily *Aedes aegypti*).",
                risk_factors="Living or traveling in tropical areas. Prior infection with a dengue virus increases your risk of severe symptoms if you're infected again with a different viral strain.",
                symptoms="**Classic Symptoms:**<br><ul><li>Sudden, high fever (often 104°F/40°C)</li><li>Severe headache and pain behind the eyes</li><li>Severe joint and muscle pain (often called 'breakbone fever')</li><li>Fatigue</li><li>Nausea and vomiting</li><li>Skin rash</li></ul>",
                diagnosis="Diagnosed using blood tests to check for the virus or antibodies to it. Doctors will also assess symptoms and ask about recent travel.",
                treatment="There is no specific medicine to treat a dengue infection. Treatment is supportive—relieving symptoms while the body fights off the virus. Severe dengue requires emergency hospital care with IV fluids.",
                medicines="<ul><li>**Acetaminophen (Tylenol):** Recommended for pain and fever relief.</li><li>**WARNING:** Do *NOT* take Aspirin, Ibuprofen (Advil), or Naproxen (Aleve) as they can increase the risk of bleeding complications associated with dengue.</li></ul>",
                diet="**To Eat:** Easily digestible foods, copious amounts of fluids (water, oral rehydration solutions, clear soups, fresh fruit juices to replenish electrolytes). Papaya leaf extract is a common traditional remedy suggested to help boost platelet counts, though clinical evidence is mixed.<br>**To Avoid:** Dark-colored foods (can mimic blood in stool/vomit), highly spicy or greasy foods.",
                home_remedies="<ul><li>Rest as much as possible.</li><li>Drink plenty of fluids to prevent dehydration caused by fever and vomiting.</li><li>Use a cool sponge bath to help reduce the fever.</li></ul>",
                prevention="The best prevention is avoiding mosquito bites. Use EPA-registered insect repellent, wear long clothing, remove standing water around your home (where mosquitoes breed), and use screens on windows and doors. A vaccine is available in some areas for those who have had previous dengue infections.",
                recovery_time="The acute phase of the illness with fever and severe pain usually lasts about a week. However, extreme fatigue and weakness can persist for several weeks after the fever breaks.",
                when_to_see_doctor="Go to the emergency room immediately if, 1-2 days after your fever goes away, you develop warning signs like: Severe abdominal pain, persistent vomiting, bleeding from your gums or nose, blood in your urine or stool, or difficulty breathing."
            )
        ]
        
        # Additional massive disease injection from external seed files
        extra_data = []
        extra_data.extend(get_infectious_diseases())
        extra_data.extend(get_lifestyle_respiratory_diseases())
        extra_data.extend(get_digestive_skin_diseases())
        extra_data.extend(get_deficiency_diseases())
        
        for item in extra_data:
            demo_articles.append(Article(**item))
            
        db.session.bulk_save_objects(demo_articles)
        db.session.commit()
        print(f"Database initialized with {len(demo_articles)} expanded demo articles.")

# Ensure DB is initialized before first request
with app.app_context():
    init_db()

if __name__ == '__main__':
    # Run server locally
    app.run(debug=True, port=5000)

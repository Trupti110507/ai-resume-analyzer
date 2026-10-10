"""
Predefined skill list for the AI Resume Analyzer.

Each entry is: (skill name, category, other ways the skill is written).
The skill name is what the user sees. The "aliases" are extra spellings the
system also accepts, so that "JS" and "JavaScript" count as the same skill.

To teach the system a new skill, add one line here and restart the application.
"""

SKILLS = [
    # ---------------- Programming languages ----------------
    ("Python", "Programming Language", ["python3"]),
    ("Java", "Programming Language", ["core java", "advanced java"]),
    ("C", "Programming Language", ["c programming", "c language"]),
    ("C++", "Programming Language", ["cpp"]),
    ("C#", "Programming Language", ["c sharp", "csharp"]),
    ("JavaScript", "Programming Language", ["js", "java script", "es6"]),
    ("TypeScript", "Programming Language", ["ts"]),
    ("PHP", "Programming Language", []),
    ("Kotlin", "Programming Language", []),
    ("Swift", "Programming Language", []),
    ("Go", "Programming Language", ["golang", "go programming", "go language"]),
    ("Ruby", "Programming Language", []),
    ("R", "Programming Language", ["r programming", "r language", "rstudio"]),
    ("Dart", "Programming Language", []),
    ("MATLAB", "Programming Language", []),
    ("Shell Scripting", "Programming Language", ["bash", "shell script", "shell scripts"]),

    # ---------------- Web technologies ----------------
    ("HTML", "Web Technology", ["html5"]),
    ("CSS", "Web Technology", ["css3"]),
    ("Bootstrap", "Web Technology", []),
    ("Tailwind CSS", "Web Technology", ["tailwind"]),
    ("jQuery", "Web Technology", []),
    ("AJAX", "Web Technology", []),
    ("JSON", "Web Technology", []),
    ("XML", "Web Technology", []),
    ("REST API", "Web Technology", ["rest apis", "restful api", "restful apis", "restful", "web services", "api development", "apis"]),
    ("Responsive Design", "Web Technology", ["responsive web design", "responsive"]),
    ("WordPress", "Web Technology", []),

    # ---------------- Frameworks and libraries ----------------
    ("Flask", "Framework", []),
    ("Django", "Framework", []),
    ("FastAPI", "Framework", []),
    ("React", "Framework", ["react.js", "reactjs"]),
    ("Angular", "Framework", ["angularjs"]),
    ("Vue.js", "Framework", ["vue", "vuejs"]),
    ("Node.js", "Framework", ["node", "nodejs"]),
    ("Express.js", "Framework", ["expressjs"]),
    ("Spring Boot", "Framework", ["spring", "springboot"]),
    ("Hibernate", "Framework", []),
    ("ASP.NET", "Framework", [".net", "dotnet", "asp.net core"]),
    ("Laravel", "Framework", []),
    ("Flutter", "Framework", []),
    ("React Native", "Framework", []),
    ("Android Development", "Framework", ["android", "android studio"]),

    # ---------------- Databases ----------------
    ("SQL", "Database", ["structured query language", "sql queries"]),
    ("MySQL", "Database", []),
    ("PostgreSQL", "Database", ["postgres"]),
    ("SQLite", "Database", []),
    ("Oracle", "Database", ["oracle database", "pl/sql", "plsql"]),
    ("SQL Server", "Database", ["ms sql", "mssql", "microsoft sql server"]),
    ("MongoDB", "Database", ["mongo"]),
    ("Firebase", "Database", []),
    ("Redis", "Database", []),
    ("DBMS", "Database", ["rdbms", "database management", "database management system", "database design"]),

    # ---------------- Data science and AI ----------------
    ("Machine Learning", "Data and AI", ["ml"]),
    ("Deep Learning", "Data and AI", []),
    ("Artificial Intelligence", "Data and AI", ["ai"]),
    ("Natural Language Processing", "Data and AI", ["nlp"]),
    ("Data Analysis", "Data and AI", ["data analytics", "data analyst"]),
    ("Data Visualization", "Data and AI", ["data visualisation"]),
    ("Data Science", "Data and AI", []),
    ("Pandas", "Data and AI", []),
    ("NumPy", "Data and AI", []),
    ("Matplotlib", "Data and AI", []),
    ("Scikit-learn", "Data and AI", ["sklearn", "scikit learn"]),
    ("TensorFlow", "Data and AI", []),
    ("PyTorch", "Data and AI", []),
    ("Keras", "Data and AI", []),
    ("OpenCV", "Data and AI", ["computer vision"]),
    ("NLTK", "Data and AI", []),
    ("spaCy", "Data and AI", []),
    ("Statistics", "Data and AI", ["statistical analysis"]),
    ("Power BI", "Data and AI", ["powerbi"]),
    ("Tableau", "Data and AI", []),
    ("MS Excel", "Data and AI", ["excel", "microsoft excel", "advanced excel"]),

    # ---------------- Tools ----------------
    ("Git", "Tool", []),
    ("GitHub", "Tool", []),
    ("GitLab", "Tool", []),
    ("VS Code", "Tool", ["visual studio code", "vscode"]),
    ("Eclipse", "Tool", []),
    ("IntelliJ IDEA", "Tool", ["intellij"]),
    ("PyCharm", "Tool", []),
    ("Jupyter Notebook", "Tool", ["jupyter"]),
    ("Postman", "Tool", []),
    ("Jira", "Tool", []),
    ("Figma", "Tool", []),
    ("Photoshop", "Tool", ["adobe photoshop"]),
    ("Canva", "Tool", []),
    ("MS Office", "Tool", ["microsoft office", "ms word", "microsoft word", "powerpoint", "ms powerpoint"]),

    # ---------------- Cloud and DevOps ----------------
    ("AWS", "Cloud and DevOps", ["amazon web services"]),
    ("Azure", "Cloud and DevOps", ["microsoft azure"]),
    ("Google Cloud", "Cloud and DevOps", ["gcp", "google cloud platform"]),
    ("Docker", "Cloud and DevOps", []),
    ("Kubernetes", "Cloud and DevOps", ["k8s"]),
    ("Jenkins", "Cloud and DevOps", []),
    ("CI/CD", "Cloud and DevOps", ["ci cd", "continuous integration"]),
    ("Linux", "Cloud and DevOps", ["ubuntu", "unix"]),
    ("Cloud Computing", "Cloud and DevOps", ["cloud"]),

    # ---------------- Computer science concepts ----------------
    ("Data Structures", "Core Concept", ["data structure", "dsa", "data structures and algorithms"]),
    ("Algorithms", "Core Concept", ["algorithm"]),
    ("Object-Oriented Programming", "Core Concept", ["oop", "oops", "object oriented programming", "object-oriented", "object oriented"]),
    ("Operating Systems", "Core Concept", ["operating system"]),
    ("Computer Networks", "Core Concept", ["computer networking", "networking", "computer network"]),
    ("Software Engineering", "Core Concept", ["sdlc", "software development life cycle"]),
    ("Software Testing", "Core Concept", ["testing", "manual testing", "unit testing", "test cases"]),
    ("Automation Testing", "Core Concept", ["selenium", "test automation"]),
    ("Debugging", "Core Concept", ["debug", "troubleshooting"]),
    ("Agile", "Core Concept", ["scrum", "agile methodology"]),
    ("UML", "Core Concept", ["unified modeling language"]),
    ("Web Development", "Core Concept", ["web developer", "web application", "web applications"]),
    ("Cyber Security", "Core Concept", ["cybersecurity", "information security", "network security"]),
    ("UI/UX Design", "Core Concept", ["ui/ux", "ui ux", "user interface design", "ux design", "ui design"]),

    # ---------------- Soft skills ----------------
    ("Communication", "Soft Skill", ["communication skills", "verbal communication", "written communication"]),
    ("Teamwork", "Soft Skill", ["team work", "team player", "collaboration", "collaborative"]),
    ("Problem Solving", "Soft Skill", ["problem-solving", "analytical skills", "analytical thinking"]),
    ("Leadership", "Soft Skill", ["team lead", "team leader"]),
    ("Time Management", "Soft Skill", []),
    ("Presentation", "Soft Skill", ["presentation skills"]),
    ("Documentation", "Soft Skill", ["technical writing", "technical documentation"]),
]

# Common English words that carry no meaning for matching ("stop words").
STOP_WORDS = set("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers him his how i if in into is it its just me more most my no nor not now of
off on once only or other our ours out over own same she should so some such than that the their
them then there these they this those through to too under until up very was we were what when
where which while who whom why will with would you your yours etc per via also may must shall
""".split())

# Words that appear in almost every job description, so they are not useful keywords.
JOB_FILLER_WORDS = set("""
job role position candidate candidates applicant applicants company organisation organization team
teams work working works experience experienced knowledge skills skill ability able good strong
excellent required requirement requirements require requires preferred responsibilities
responsibility responsible looking seeking join opportunity year years month months fresher
freshers graduate graduates degree bachelor bachelors master masters qualification qualifications
including include includes using use used well new help need needs will plus like basic
understanding familiarity familiar hands proficiency proficient understand apply location salary
description title intern internship junior senior developer engineer developers engineers
development develop developing build building design designing write writing maintain create
ensure provide support based related various within across day time full part
""".split())

from flask import Flask, render_template, request
from neo4j import GraphDatabase
import os

app = Flask(__name__)

# Neo4j connection
NEO4J_URI = "neo4j+s://1651f036.databases.neo4j.io"  # Update with your URI
NEO4J_USER = "neo4j"  # Update with your username
NEO4J_PASSWORD = "5lm2lFChvqj_8wNR36NQj-mTU-HIWeTP6TwoXcDQo6U" # Update with your password

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_all_terms(language=None):
    """Get all terms from database (for dropdown)"""
    with driver.session() as session:
        if language:
            query = """
            MATCH (t:Term {language: $language})
            RETURN t.name as name
            ORDER BY t.name
            """
            result = session.run(query, language=language)
        else:
            query = """
            MATCH (t:Term)
            RETURN t.name as name, t.language as language
            ORDER BY t.language, t.name
            """
            result = session.run(query)
        
        terms = []
        for record in result:
            if 'language' in record:
                terms.append(f"{record['name']} ({record['language']})")
            else:
                terms.append(record['name'])
        return terms

@app.route('/')
def index():
    """Home page with search"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Search for a term"""
    term = request.form.get('term', '').strip()
    language = request.form.get('language', 'EN')
    
    if not term:
        return render_template('index.html', error="Please enter a search term")
    
    # Get the term with its relationships
    with driver.session() as session:
        query = """
        MATCH (t:Term {name: $term, language: $language})
        OPTIONAL MATCH (t)-[:BROADER_TERM]->(bt:Term)
        OPTIONAL MATCH (t)-[:NARROWER_TERM]->(nt:Term)
        OPTIONAL MATCH (t)-[:RELATED_TERM]->(rt:Term)
        OPTIONAL MATCH (t)-[:USED_FOR]->(uf:Term)
        OPTIONAL MATCH (t)-[:PART_OF]->(po:Term)
        OPTIONAL MATCH (t)-[:LANGUAGE_EQUIVALENT]->(le:Term)
        RETURN t.name as term,
               t.language as language,
               t.scope_notes as scope_notes,
               COLLECT(DISTINCT bt.name) as broader_terms,
               COLLECT(DISTINCT nt.name) as narrower_terms,
               COLLECT(DISTINCT rt.name) as related_terms,
               COLLECT(DISTINCT uf.name) as used_for,
               COLLECT(DISTINCT po.name) as part_of,
               COLLECT(DISTINCT le.name) as language_equivalents
        """
        
        result = session.run(query, term=term, language=language)
        record = result.single()
    
    if not record or not record['term']:
        return render_template('index.html', 
                             error=f'Term "{term}" not found in {language}')
    
    # Get equivalents in other languages
    equivalents = {}
    if record['language_equivalents']:
        with driver.session() as session:
            for equiv_term in record['language_equivalents']:
                if equiv_term:  # Check if not None
                    # Find which language this equivalent is in
                    lang_query = """
                    MATCH (t:Term {name: $term})
                    WHERE t.language IN ['EN', 'RU', 'KZ']
                    RETURN t.language as language
                    """
                    lang_result = session.run(lang_query, term=equiv_term)
                    lang_record = lang_result.single()
                    
                    if lang_record:
                        # Get the equivalent term's details
                        equiv_query = """
                        MATCH (t:Term {name: $term, language: $lang})
                        OPTIONAL MATCH (t)-[:BROADER_TERM]->(bt:Term)
                        OPTIONAL MATCH (t)-[:NARROWER_TERM]->(nt:Term)
                        OPTIONAL MATCH (t)-[:RELATED_TERM]->(rt:Term)
                        OPTIONAL MATCH (t)-[:USED_FOR]->(uf:Term)
                        OPTIONAL MATCH (t)-[:PART_OF]->(po:Term)
                        RETURN t.name as term,
                               t.language as language,
                               t.scope_notes as scope_notes,
                               COLLECT(DISTINCT bt.name) as broader_terms,
                               COLLECT(DISTINCT nt.name) as narrower_terms,
                               COLLECT(DISTINCT rt.name) as related_terms,
                               COLLECT(DISTINCT uf.name) as used_for,
                               COLLECT(DISTINCT po.name) as part_of
                        """
                        
                        equiv_result = session.run(equiv_query, term=equiv_term, lang=lang_record['language'])
                        equiv_record = equiv_result.single()
                        
                        if equiv_record:
                            lang = equiv_record['language']
                            equivalents[lang] = {
                                'term': equiv_record['term'],
                                'language': lang,
                                'scope_notes': equiv_record['scope_notes'] or [],
                                'relations': {
                                    'BROADER_TERM': [{'term': term, 'language': lang} for term in equiv_record['broader_terms'] if term],
                                    'NARROWER_TERM': [{'term': term, 'language': lang} for term in equiv_record['narrower_terms'] if term],
                                    'RELATED_TERM': [{'term': term, 'language': lang} for term in equiv_record['related_terms'] if term],
                                    'USED_FOR': [{'term': term, 'language': lang} for term in equiv_record['used_for'] if term],
                                    'PART_OF': [{'term': term, 'language': lang} for term in equiv_record['part_of'] if term],
                                    'LANGUAGE_EQUIVALENT': []
                                }
                            }
    
    # Add the main term to results
    results_by_language = {}
    
    # Main term
    main_lang = record['language']
    results_by_language[main_lang] = {
        'term': record['term'],
        'language': main_lang,
        'scope_notes': record['scope_notes'] or [],
        'relations': {
            'BROADER_TERM': [{'term': term, 'language': main_lang} for term in record['broader_terms'] if term],
            'NARROWER_TERM': [{'term': term, 'language': main_lang} for term in record['narrower_terms'] if term],
            'RELATED_TERM': [{'term': term, 'language': main_lang} for term in record['related_terms'] if term],
            'USED_FOR': [{'term': term, 'language': main_lang} for term in record['used_for'] if term],
            'PART_OF': [{'term': term, 'language': main_lang} for term in record['part_of'] if term],
            'LANGUAGE_EQUIVALENT': [{'term': term, 'language': '?'} for term in record['language_equivalents'] if term]
        }
    }
    
    # Add equivalents
    for lang, data in equivalents.items():
        results_by_language[lang] = data
    
    # Get all terms for dropdown in add form
    all_terms = get_all_terms()
    
    return render_template('index.html', 
                         search_term=term,
                         search_language=language,
                         results=results_by_language,
                         all_terms=all_terms)

@app.route('/add-term', methods=['POST'])
def add_term():
    """Add a new term with optional relationships"""
    term = request.form.get('term', '').strip()
    language = request.form.get('language', 'EN')
    scope_note = request.form.get('scope_note', '').strip()
    
    # Get relationship data if provided
    related_term = request.form.get('related_term', '').strip()
    relation_type = request.form.get('relation_type', '')
    
    if not term:
        return render_template('index.html', error="Term name is required")
    
    with driver.session() as session:
        # Create the term
        create_query = """
        MERGE (t:Term {name: $term, language: $language})
        ON CREATE SET t.created_at = timestamp()
        """
        
        if scope_note:
            create_query += "SET t.scope_notes = coalesce(t.scope_notes, []) + $scope_note"
        
        session.run(create_query, term=term, language=language, scope_note=[scope_note])
        
        # If a relationship is specified, create it
        if related_term and relation_type:
            # Parse the related term (format: "term (language)" or just "term")
            if '(' in related_term and ')' in related_term:
                # Extract term and language from "term (language)"
                parts = related_term.split('(')
                related_term_name = parts[0].strip()
                related_lang = parts[1].replace(')', '').strip()
            else:
                # Just term name, use same language
                related_term_name = related_term
                related_lang = language
            
            # Map relationship type to Neo4j relationship
            rel_mapping = {
                'BT': 'BROADER_TERM',
                'NT': 'NARROWER_TERM', 
                'RT': 'RELATED_TERM',
                'UF': 'USED_FOR',
                'PT': 'PART_OF',
                'LE': 'LANGUAGE_EQUIVALENT'
            }
            
            neo4j_rel = rel_mapping.get(relation_type, 'RELATES_TO')
            
            # Check if related term exists, create if not
            check_query = """
            MERGE (rt:Term {name: $related_term, language: $related_lang})
            """
            session.run(check_query, related_term=related_term_name, related_lang=related_lang)
            
            # Create the relationship
            if relation_type == 'BT':
                # BT: New term is narrower than related term (new term -> related term is BROADER)
                rel_query = f"""
                MATCH (t:Term {{name: $term, language: $lang}})
                MATCH (rt:Term {{name: $related_term, language: $related_lang}})
                MERGE (t)-[:{neo4j_rel}]->(rt)
                """
            elif relation_type == 'NT':
                # NT: New term is broader than related term (new term <- related term is NARROWER)
                # Actually NT means new term has narrower terms, so related term is narrower than new term
                # So: related term -> new term is NARROWER_TERM
                rel_query = f"""
                MATCH (t:Term {{name: $term, language: $lang}})
                MATCH (rt:Term {{name: $related_term, language: $related_lang}})
                MERGE (rt)-[:{neo4j_rel}]->(t)
                """
            elif relation_type == 'LE':
                # LE: Create bidirectional language equivalent
                rel_query = f"""
                MATCH (t:Term {{name: $term, language: $lang}})
                MATCH (rt:Term {{name: $related_term, language: $related_lang}})
                MERGE (t)-[:{neo4j_rel}]->(rt)
                MERGE (rt)-[:{neo4j_rel}]->(t)
                """
            else:
                # For RT, UF, PT: new term -> related term
                rel_query = f"""
                MATCH (t:Term {{name: $term, language: $lang}})
                MATCH (rt:Term {{name: $related_term, language: $related_lang}})
                MERGE (t)-[:{neo4j_rel}]->(rt)
                """
            
            session.run(rel_query, 
                       term=term, lang=language,
                       related_term=related_term_name, related_lang=related_lang)
    
    # Get all terms for dropdown
    all_terms = get_all_terms()
    
    return render_template('index.html', 
                         success=f'Term "{term}" added successfully in {language}',
                         all_terms=all_terms)

if __name__ == '__main__':
    app.run(debug=True, port=5000)


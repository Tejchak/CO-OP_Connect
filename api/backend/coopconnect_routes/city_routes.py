from flask import Blueprint
from flask import request
from flask import jsonify
from flask import make_response
from flask import current_app
from backend.db_connection import db


#returns a list of all cities
cities = Blueprint('City', __name__)

@cities.route('/city', methods=['GET'])
def get_all_cities():
    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM City")
        cities_data = cursor.fetchall()
        cursor.close()

        cities_list = []
        for city in cities_data:
            cities_list.append({
                'city_id': city[0],
                'avg_cost_of_living': city[1],
                'avg_rent': city[2],
                'avg_wage': city[3],
                'name': city[4],
                'population': city[5],
                'prop_hybrid_workers': float(city[6]) if city[6] else None
            })

        return jsonify(cities_list), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#returns the details of a specific city
@cities.route('/city/<CityID>', methods=['GET'])
def get_city_details(CityID):
    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT City_ID, Avg_Cost_Of_Living, Avg_Rent, Avg_Wage, 
                   Name, Population, Prop_Hybrid_Workers 
            FROM City 
            WHERE Name = (Select Name FROM City WHERE City_ID = %s)
        """, (CityID,))
        city_data = cursor.fetchall()
        cursor.close()

        if not city_data:
            return jsonify({'error': 'City not found'}), 404

        city_details = {
            'city_id': city_data[0],
            'avg_cost_of_living': city_data[1],
            'avg_rent': city_data[2],
            'avg_wage': city_data[3],
            'name': city_data[4],
            'population': city_data[5],
            'prop_hybrid_workers': float(city_data[6]) if city_data[6] else None
        }

        return jsonify(city_details), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


#returns the cost analysis of a specific city
@cities.route('/city/<CityID>/<Avg_Cost_Of_Living>', methods=['GET'])
def get_city_cost_analysis(CityID, Avg_Cost_Of_Living):
    try:
        # Get a cursor within an app context
        with current_app.app_context():
            cursor = db.get_db.cursor()
            target_cost = int(Avg_Cost_Of_Living)
            
            # Debug: Print available costs
            cursor.execute("SELECT Name, Avg_Cost_Of_Living FROM City")
            all_cities = cursor.fetchall()
            print(f"Available cities and costs: {all_cities}")
            print(f"Target cost: {target_cost}")
            
            # Modified query with wider range and debug
            margin = target_cost * 0.2  # Increased to 20% range
            min_cost = target_cost - margin
            max_cost = target_cost + margin
            
            print(f"Looking for cities with cost between {min_cost} and {max_cost}")
            
            query = """
                SELECT c1.Name, 
                       c1.Avg_Cost_Of_Living,
                       c1.Avg_Rent,
                       c1.Avg_Wage,
                       c1.Avg_Cost_Of_Living / c1.Avg_Wage as cost_to_wage_ratio,
                       c1.Avg_Rent / c1.Avg_Wage as rent_to_wage_ratio,
                       (SELECT AVG(Avg_Cost_Of_Living) FROM City) as avg_national_col,
                       (SELECT AVG(Avg_Rent) FROM City) as avg_national_rent,
                       (SELECT AVG(Avg_Wage) FROM City) as avg_national_wage
                FROM City c1
                WHERE c1.Avg_Cost_Of_Living BETWEEN %s AND %s
                ORDER BY ABS(c1.Avg_Cost_Of_Living - %s)
                LIMIT 1
            """
            print(f"Executing query: {query}")
            print(f"With parameters: {(min_cost, max_cost, target_cost)}")
            
            cursor.execute(query, (min_cost, max_cost, target_cost))
            city_data = cursor.fetchone()
            print(f"Query result: {city_data}")
            cursor.close()

            if not city_data:
                return jsonify({
                    'error': 'No cities found matching the specified cost of living',
                    'debug': {
                        'target_cost': target_cost,
                        'min_cost': min_cost,
                        'max_cost': max_cost,
                        'available_cities': all_cities
                    }
                }), 404

            cost_analysis = {
                'name': city_data[0],
                'cost_of_living': float(city_data[1]),
                'avg_rent': float(city_data[2]),
                'avg_wage': float(city_data[3]),
                'cost_metrics': {
                    'cost_to_wage_ratio': float(city_data[4]),
                    'rent_to_wage_ratio': float(city_data[5]),
                    'cost_vs_national_avg': {
                        'cost_of_living_percent': (city_data[1] / city_data[6] * 100) - 100,
                        'rent_percent': (city_data[2] / city_data[7] * 100) - 100,
                        'wage_percent': (city_data[3] / city_data[8] * 100) - 100
                    }
                }
            }

            return jsonify(cost_analysis), 200

    except Exception as e:
        print(f"Error in get_city_cost_analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500

#Finds cities with a similar proportion of hybrid workers
@cities.route('/city/<CityID>/<Prop_Hybrid_Workers>', methods=['GET'])
def get_cities_by_hybrid_proportion(Prop_Hybrid_Workers):
    try:
        # Validate input range (0-1)
        if not 0 <= Prop_Hybrid_Workers <= 1:
            return jsonify({'error': 'Target proportion must be between 0 and 1'}), 400

        cursor = db.cursor()
        
        # Find cities within ±10% of target proportion, ordered by closest match
        cursor.execute("""
            SELECT 
                Name,
                Prop_Hybrid_Workers,
                Avg_Cost_Of_Living,
                Avg_Rent,
                Avg_Wage,
                Population,
                ABS(Prop_Hybrid_Workers - %s) as proportion_difference
            FROM City
            WHERE Prop_Hybrid_Workers BETWEEN %s - 0.1 AND %s + 0.1
            ORDER BY proportion_difference ASC
        """, (Prop_Hybrid_Workers, Prop_Hybrid_Workers, Prop_Hybrid_Workers))
        
        cities_data = cursor.fetchall()
        cursor.close()

        if not cities_data:
            return jsonify({'message': 'No cities found matching the target hybrid work proportion',
                          'cities': []}), 200

        cities_list = []
        for city in cities_data:
            cities_list.append({
                'name': city[0],
                'prop_hybrid_workers': float(city[1]),
                'avg_cost_of_living': city[2],
                'avg_rent': city[3],
                'avg_wage': city[4],
                'population': city[5],
                'difference_from_target': float(city[6])
            })

        response = {
            'target_proportion': Prop_Hybrid_Workers,
            'cities_found': len(cities_list),
            'cities': cities_list
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cities.route('/city/test', methods=['GET'])
def test_route():
    return jsonify({"message": "City routes are working"}), 200




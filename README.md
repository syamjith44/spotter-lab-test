# Route Planner Django Service

A simple Django-based backend service for:

* Geocoding locations
* Finding fuel cost–optimized routes

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env` file

Create a `.env` file in the root directory and add:

```
GEO_CODER_API_KEY=your_api_key
ROUTE_API_KEY=your_api_key
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Run the server

```bash
python manage.py runserver
```

---

## APIs

### 1. Geocode API

**Endpoint:**

```
POST /route-planner/geocode/
```

**Payload:**

```json
{
    "start_point": "1301 Chalk Hill Rd, Dallas, TX",
    "end_point": "2617 Democrat Rd, Memphis, TN"
}
```

**Response:**

```json
{
    "start_point": [
        "-96.9021848",
        "32.7609044"
    ],
    "end_point": [
        "-89.9769041",
        "35.0688404"
    ]
}
```

---

### 2. Fuel-Optimized Route API

**Endpoint:**

```
POST /route-planner/fuel-stations/route/
```

**Payload:**

```json
{
    "start_point": [
        "-96.9021848",
        "32.7609044"
    ],
    "end_point": [
        "-89.9769041",
        "35.0688404"
    ]
}
```

**Response (simplified):**

```json
{
    "fuel_plan": {
        "optimal_stops": [...],
        "leg_details": [...],
        "total_cost_usd": ...,
        "total_gallons": ...,
        "number_of_stops": ...,
        "total_distance": ...
    },
    "polyline": [...]
}
```

---

## Notes

* Ensure valid API keys are configured in `.env`
* Migrations must be run before starting the server

---

## Tech Stack

* Django
* Python

---

## Author

Syamjith P

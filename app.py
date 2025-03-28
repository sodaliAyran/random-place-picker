import os

import uvicorn
from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from apscheduler.schedulers.background import BackgroundScheduler
import random
import datetime

import logging

from fastapi.middleware.cors import CORSMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
TODAY_CHOICES = "today_choices"
FINAL_PLACE = "final_place"
GATHERING_TIME = "gathering_time"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class Place(Base):
    __tablename__ = "places"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class AvailableHour(Base):
    __tablename__ = "available_hours"
    id = Column(Integer, primary_key=True, index=True)
    time = Column(String, unique=True, nullable=False)  # e.g., "18:00", "18:30", ...


class DailySelection(Base):
    __tablename__ = "daily_selection"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.date.today, unique=True)
    places = Column(String)  # Comma-separated list of places
    gathering_time = Column(DateTime, nullable=False)
    final_place = Column(String, nullable=True)


Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8081", "https://bugunneredeyiz.onrender.com/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache
CACHE = {TODAY_CHOICES: None, FINAL_PLACE: None, GATHERING_TIME: None}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_available_places(db: Session):
    try:
        return [place.name for place in db.query(Place).all()]
    except Exception as e:
        logger.error(f"Error fetching places: {e}")
        return []

def get_available_hours(db: Session):
    try:
        return [hour.time for hour in db.query(AvailableHour).all()]
    except Exception as e:
        logger.error(f"Error fetching available hours: {e}")
        return []

def get_today_selection(db: Session):
    try:
        return db.query(DailySelection).filter(
            func.date(DailySelection.date) == datetime.date.today()).first()
    except Exception as e:
        logger.error(f"Error fetching today's selection: {e}")
        return

""" Picks 3-5 random places and a gathering time, stores in the cache and database."""
def pick_places():
    db = next(get_db())
    try:
        selected_places, gathering_time = _pick_place_and_time(*_get_available_places_and_hours(db))
        _store_in_cache(selected_places, gathering_time)
        _store_in_db(db, selected_places, gathering_time)
    except Exception as e:
        logger.error(f"Error selecting places: {e}")
    finally:
        db.close()

def _get_available_places_and_hours(db):
    available_places = get_available_places(db)
    available_hours = get_available_hours(db)
    if not available_places or not available_hours:
        logger.error("No places or available hours found.")
        return
    return available_places, available_hours

def _pick_place_and_time(available_places, available_hours):
    num_places = random.randint(3, 5)
    selected_places = random.sample(available_places, num_places)
    gathering_time_str = random.choice(available_hours)
    gathering_time = datetime.datetime.strptime(gathering_time_str, "%H:%M").time()

    logger.info(f"Selected places for today: {selected_places}")
    logger.info(f"Selected gathering time for today: {gathering_time}")

    return selected_places, gathering_time

def _store_in_cache(selected_places, gathering_time):
    CACHE[TODAY_CHOICES] = selected_places
    CACHE[GATHERING_TIME] = gathering_time

def _store_in_db(db, selected_places, gathering_time):
    selection = DailySelection(
        places=",".join(selected_places),
        gathering_time=datetime.datetime.combine(datetime.date.today(), gathering_time)
    )
    db.add(selection)
    db.commit()
    db.refresh(selection)
    db.close()

""" Picks a final place 2 hours before the gathering time and updates the DB and cache."""
def pick_final_place():
    if CACHE[FINAL_PLACE]:
        logger.info("Final place already selected.")
        return

    db = next(get_db())
    selected_places, gathering_time = CACHE[TODAY_CHOICES], CACHE[GATHERING_TIME]
    if not (selected_places and gathering_time):
        selected_places, gathering_time = _get_places_and_gathering_time_from_db(db)
        _store_in_cache(selected_places, gathering_time)
    if not (selected_places and gathering_time):
        logger.error("Error getting today's selections")
        db.close()
        return

    if _is_within_two_hours_from_now(gathering_time):
        _set_final_place(db, selected_places)

def _get_places_and_gathering_time_from_db(db):
    try:
        today_selection = get_today_selection(db)
        if not today_selection:
            logger.error("No daily selection found in DB.")
            return
        return today_selection.places.split(","), today_selection.gathering_time
    except Exception as e:
        logger.error(f"Error getting today's selection: {e}")
        return

def _set_final_place(db, selected_places):
    try:
        final_place = random.choice(selected_places)
        logger.info(f"Final place selected: {final_place}")
        CACHE[FINAL_PLACE] = final_place
        today_selection = get_today_selection(db)
        if today_selection:
            today_selection.final_place = final_place
            db.commit()
            db.refresh(today_selection)
        else:
            logger.error(f"Error setting final place to database")
    except Exception as e:
        logger.error(f"Error setting final place to database: {e}")
    finally:
        db.close()


def _is_within_two_hours_from_now(gathering_time):
    current_datetime = datetime.datetime.now()
    time_difference = gathering_time - current_datetime
    print(time_difference.total_seconds())
    return time_difference.total_seconds() <= 2 * 60 * 60

scheduler = BackgroundScheduler()
scheduler.add_job(pick_places, "cron", hour=0, minute=0)  # Pick new places and time every midnight
scheduler.add_job(pick_final_place, "interval", minutes=15)  # Check every 15 minutes to pick the final place
scheduler.start()

""" Returns the daily selected places, gathering time, and final place if selected."""
@app.get("/choices")
def get_choices(db: Session = Depends(get_db)):
    selected_places, gathering_time = CACHE[TODAY_CHOICES], CACHE[GATHERING_TIME]
    if not (selected_places and gathering_time):
        selected_places, gathering_time = _get_places_and_gathering_time_from_db(db)
        _store_in_cache(selected_places, gathering_time)
    if not (selected_places and gathering_time):
        return {"message": "No selection made yet."}
    response = {
        TODAY_CHOICES: selected_places,
        GATHERING_TIME: gathering_time
    }

    # Check if final place is selected
    if CACHE[FINAL_PLACE]:
        response[FINAL_PLACE] = CACHE[FINAL_PLACE]
    else:
        if _is_within_two_hours_from_now(gathering_time):
            # Unoptimized DB query. We should not re-query the db if we already did above.
            # But that requires a bit of refactor
            today_selection = get_today_selection(db)
            if today_selection and today_selection.final_place:
                response[FINAL_PLACE] = today_selection.final_place
                CACHE[FINAL_PLACE] = today_selection.final_place
    return response

@app.get("/healthz")
def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow()}

if __name__ == "__main__":
    uvicorn.run(app, reload=False, log_level=logging.INFO)
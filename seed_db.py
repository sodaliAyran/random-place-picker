import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import random
import datetime

from app import Base, Place, AvailableHour, DailySelection

# SQLite database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Sample data for seeding
places = [
    "Taksim İstiklal Caddesi",
    "Kadıköy Rıhtım",
    "Saraçhane",
    "Şişli Kurtuluş Caddesi",
    "Levent Sapphire Önü",
    "Beşiktaş Barbaros Bulvarı",
    "FSM Köprüsü",
    "Dolmabahçe Sarayı",
    "Maçka Parkı",
    "Taksim Gezi Parkı",
    "Bağdat Caddesi Suadiye Işıklar"
]

available_hours = [
    "18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"
]

# Function to seed the database
def seed_db():
    db = SessionLocal()

    try:
        # Create tables if they don't exist yet
        Base.metadata.create_all(bind=engine)  # This creates the tables

        # Seed Places
        if db.query(Place).count() == 0:  # Check if the table is empty
            for place in places:
                new_place = Place(name=place)
                db.add(new_place)
            db.commit()  # Commit the transaction

        # Seed Available Hours
        if db.query(AvailableHour).count() == 0:  # Check if the table is empty
            for hour in available_hours:
                new_hour = AvailableHour(time=hour)
                db.add(new_hour)
            db.commit()  # Commit the transaction

        # Seed Daily Selection (for today)
        if db.query(DailySelection).count() == 0:  # Check if the table is empty
            selected_places = random.sample(places, random.randint(3, 5))  # Pick 3-5 random places
            gathering_time_str = random.choice(available_hours)  # Pick a random gathering time

            # Convert gathering_time_str to a time object
            gathering_time = datetime.datetime.strptime(gathering_time_str, "%H:%M").time()
            gathering_datetime = datetime.datetime.combine(datetime.date.today(), gathering_time)

            # Create the selection for today
            new_selection = DailySelection(
                date=datetime.date.today(),  # Use today's date as a datetime.date object
                places=",".join(selected_places),  # Comma-separated list of places
                gathering_time=gathering_datetime  # Use the time object for gathering time
            )
            db.add(new_selection)
            db.commit()  # Commit the transaction

    except Exception as e:
        db.rollback()  # Rollback in case of error
        print(f"Error seeding the database: {e}")
    finally:
        db.close()  # Close the session

# Run the seeding function
if __name__ == "__main__":
    seed_db()  # Seed the database with initial data
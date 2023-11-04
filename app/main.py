import uvicorn
import os
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi_sqlalchemy import DBSessionMiddleware, db

from soc_cars_core.schemas.admin_schema import CreateCar as SchemaCreateCar, CreateUser as SchemaCreateAdmin, ListUser as SchemaListUser, \
UpdateCar as SchemaUpdateCar, ListCar as SchemaListCar
from soc_cars_core.schemas.auth_schema import Token
from soc_cars_core.models import Car, User, UserRental

from soc_cars_core.utils import check_if_user_exists
from soc_cars_core.auth import get_password_hash, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, get_current_active_admin
from typing import List, Annotated

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


app = FastAPI(title="Car Rental Admin")

# to avoid csrftokenError
app.add_middleware(DBSessionMiddleware, db_url=os.environ['DATABASE_URL'])




# @app.get('/book/')
# async def book():
#     book = db.session.query(ModelBook).all()
#     return book

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

  
@app.post('/admins/create', response_model=SchemaListUser)
async def create_admin(user:SchemaCreateAdmin):
    if check_if_user_exists(user.email):
        raise HTTPException(status_code=400, detail="User with this email already exist")
    pwd_hash = get_password_hash(user.password)
    db_user = User(name=user.name, email=user.email, phone_number=user.phone_number, address=user.address, password=pwd_hash, is_admin=True)
    db.session.add(db_user)
    db.session.commit()
    return db_user

@app.get('/admins', response_model=List[SchemaListUser])
async def admins(
    current_user: User = Depends(get_current_active_admin)
):
    author = db.session.query(User).filter_by(is_admin=True).all()
    return author


@app.post('/car/create', response_model=SchemaListCar)
async def create_car(car: SchemaCreateCar, current_user: User = Depends(get_current_active_admin)):
    db_car = Car(name=car.name, car_type=car.car_type, available_count = car.available_count, user_id=current_user.id, rent_per_day=car.rent_per_day)
    db.session.add(db_car)
    db.session.commit()
    return db_car


@app.get('/cars', response_model=List[SchemaListCar])
async def list_cars(
    current_user: User = Depends(get_current_active_admin)
):
    cars = db.session.query(Car).all()
    return cars


@app.patch('/car/{car_id}/update', response_model=SchemaListCar)
async def update_car(
    car_id: int, car: SchemaUpdateCar, current_user: User = Depends(get_current_active_admin)
):
    car_obj = db.session.query(Car).get(car_id)
    if not car_obj:
        raise HTTPException(status_code=404, detail="Car not found")
    car_data = car.dict(exclude_unset=True)
    for key, value in car_data.items():
        setattr(car_obj, key, value)
    db.session.add(car_obj)
    db.session.commit()
    db.session.refresh(car_obj)
    return car_obj

@app.delete('/car/{car_id}/delete')
async def delete_car(
    car_id: int, current_user: User = Depends(get_current_active_admin)
):
    car_obj = db.session.query(Car).get(car_id)
    if car_obj:
        db.session.delete(car_obj)
        db.session.commit()
    return {'status': 'success'}

@app.get('/user/pending-rentals')
async def user_pending_rentals(
    current_user: User = Depends(get_current_active_admin)
):
    rentals = db.session.query(UserRental).filter(UserRental.rental_end_date.is_(None)).order_by(UserRental.rental_started.desc())
    return [rental.serialize() for rental in rentals]

@app.get('/user/completed-rentals')
async def user_completed_rentals(
    current_user: User = Depends(get_current_active_admin)
):
    rentals = db.session.query(UserRental).filter(UserRental.rental_end_date.isnot(None)).order_by(UserRental.rental_started.desc())
    return [rental.serialize() for rental in rentals]


# # # To run locally
# # if __name__ == '__main__':
# #     uvicorn.run(app, host='0.0.0.0', port=8000)
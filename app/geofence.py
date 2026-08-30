import math

from fastapi import HTTPException, status

from app.config import settings


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    raio_terra_km = 6371.0

    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return raio_terra_km * c


def esta_na_area_piloto(latitude: float, longitude: float) -> bool:
    if not settings.AREA_PILOTO_ATIVA:
        return True

    dist = distancia_km(
        latitude, longitude,
        settings.AREA_PILOTO_LATITUDE, settings.AREA_PILOTO_LONGITUDE,
    )
    return dist <= settings.AREA_PILOTO_RAIO_KM


def validar_dentro_da_area_piloto(latitude: float, longitude: float, contexto: str = "localização") -> None:
    if not esta_na_area_piloto(latitude, longitude):
        dist = distancia_km(
            latitude, longitude,
            settings.AREA_PILOTO_LATITUDE, settings.AREA_PILOTO_LONGITUDE,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"O {contexto} está fora da área de cobertura do piloto "
                f"({settings.AREA_PILOTO_NOME}, raio de {settings.AREA_PILOTO_RAIO_KM}km). "
                f"Distância calculada: {dist:.2f}km do centro da área."
            ),
        )

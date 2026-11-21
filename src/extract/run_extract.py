from src.extract import s1_bma_rain, s2_metar, s3_openmeteo, s4_sun, s5_holidays, s6_osm, s8_bma_flood_sensors, s9_bma_open_data

SOURCES = {'bma_rain': s1_bma_rain, 'metar': s2_metar, 'openmeteo': s3_openmeteo, 'sun': s4_sun,
           'holidays': s5_holidays, 'osm': s6_osm, 'bma_flood': s8_bma_flood_sensors, 'bma_open_data': s9_bma_open_data}

if __name__ == '__main__':
    import sys
    for name, mod in SOURCES.items():
        if len(sys.argv) == 1 or name in sys.argv[1:]:
            mod.main()

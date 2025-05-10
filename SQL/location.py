import pandas as pd


def get_location_image_from_df(location_df):
    """
    Get the location image path from the first row of the dataframe.
    
    Args:
        location_df (pd.DataFrame): DataFrame containing at least a column "location".
        
    Returns:
        str: Path to the location image.
    """
    # Check if the DataFrame is empty or does not contain the 'location' column
    if location_df.empty or 'location' not in location_df.columns:
        raise ValueError("DataFrame is empty or does not contain 'location' column.")
    
    # Get the first row's location value
    location = location_df.iloc[0]['location']
    
    # I got 10 location, Stat 1, Stat 2, Stat 3, Stat 4, Stat 5, Stat 6, Stat 7, Stat 8, Amphi 1, Amphi 2
    # Create the image path based on the location value

    if "Stat 1" in location:
        image_path = "plans/STAT1.html"
    elif "Stat 2" in location:
        image_path = "plans/STAT2.html"
    elif "Stat 3" in location:
        image_path = "plans/STAT3.html"
    elif "Stat 4" in location:
        image_path = "plans/STAT4.html"
    elif "Stat 5" in location:
        image_path = "plans/STAT5.html"
    elif "Stat 6" in location:
        image_path = "plans/STAT6.html"
    elif "Stat 7" in location:
        image_path = "plans/STAT7.html"
    elif "Stat 8" in location:
        image_path = "plans/STAT8.html"
    elif "Amphi Ada" in location: 
        image_path = "plans/AmphiADA.html"
    elif "Amphi Blaise" in location:
        image_path = "plans/AmphiBLAISE.html"
    elif "S1" in location:
        image_path = "plans/S1.html"
    elif "S2" in location:
        image_path = "plans/S2.html"
    elif "S3" in location:
        image_path = "plans/S3.html"
    elif "S4" in location:
        image_path = "plans/S4.html"
    elif "S5" in location:
        image_path = "plans/S5.html"
    elif "S6" in location:
        image_path = "plans/S6.html"
    elif "S7" in location:
        image_path = "plans/S7.html"
    elif "S8" in location:
        image_path = "plans/S8.html"
    elif "ROB" in location:
        image_path = "plans/ROBOT.html"

    return image_path
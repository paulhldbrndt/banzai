from flask import Flask, render_template
import requests
from banzai_bot.utils import get_sites_and_instruments
from banzai_bot.forms import ReprocessDayObsForm


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/reprocess_dayobs')
def reprocess_dayobs():
    form = ReprocessDayObsForm()
    sites, instruments = get_sites_and_instruments()
    form.sites.choices = sites
    form.instruments.choices = instruments
    return render_template('reprocess_dayobs.html', title='Reprocess Dayobs', form=form)
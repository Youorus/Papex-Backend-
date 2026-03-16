import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "papex.settings.prod")
django.setup()

from django.utils import timezone
from django.db.models import Q

from api.leads.models import Lead
from api.comments.models import Comment
from api.lead_status.models import LeadStatus
from api.leads.constants import LeadSource, A_RAPPELER, NEW_FACEBOOK_LEAD
from api.users.models import User


# 🔧 Utilisateur système pour créer les commentaires
SYSTEM_USER_ID = "86f0ee24-f245-4318-b6b1-8a3c68e12927"  # ⚠️ adapte si besoin


# 🔥 Liste avec besoin
LEADS = [
    # AVIS CLIENT - TDS - PAPEX ACCÉLÉRER (50 leads)
    ("Juinoir", "Anaverss", "sissokohamady320@gmail.com", "+33753558498", "cv"),
    ("Suk", "Vannchanbory", "suk.vann@outlook.fr", "+33646922500", "Card séjour"),
    ("Smichi", "Zied", "kellysa@gmx.fr", "+33758127900", "Titre séjour"),
    ("Rabah", "Aouissi", "rabah_hp@yahoo.fr", "+33677672859", "TDS"),
    ("Kessie", "De Tya", "leukoyves@yahoo.com", "+33751140976", "TDS"),
    ("Georges", "Monthe", "georgesmonthe@yahoo.fr", "+33688273010", "Naturalisation et autres"),
    ("Bilelmbn", "Nahari", "bilelnahari92@gmail.com", "+33641149767", "Duplicata"),
    ("Cliff", "Pakiry", "cliffpakiry@gmail.com", "+33644894322", "Naturalisation"),
    ("Sekou", "Kamara", "sekoucamara1927@gmail.com", "+33665340478", "Sekou"),
    ("Joseph Tama Tama", "Funzi Kebo", "jtamar2024@gmail.com", "+33631897297", "TDS"),
    ("R-B-89", "", "rachid_bouh@hotmail.fr", "+33766684492", "Naturalisation française"),
    ("Mariama", "Diallo", "mariamacolon.diallo@gmail.com", "+33668092316", "Naturalisation"),
    ("Pamela", "Vingatama", "vingatamap@gmail.com", "+33765211435", "Titre de séjour vie privée et familiale"),
    ("Theresia", "Ngangue", "theresiajang.ngangue@yahoo.fr", "+33650858714", "Naturalisation"),
    ("Claudia", "Rasoarivony", "claudia-rasoarivony@outlook.fr", "+33601255979", "Renouvellement titre de séjour"),
    ("Madeleine", "Kedi", "phileojoyce@live.fr", "+33754507851", "Naturalisation"),
    ("Yannick", "Diomandé", "hermannd403@gmail.com", "+33616509624", "Naturalisation"),
    ("Irène", "Didi", "lornge94@gmail.com", "+33628073657", "Autre"),
    ("Russel", "Tegel", "tegelrussel1983@gmail.com", "+33767647759", "Naturalisation"),
    ("Yves Jean Claude", "Biabaro", "yvesjohnb@hotmail.fr", "+33613374568", "TDS"),
    ("Verratinho", "Sisko", "sislo93@me.com", "+33661386140", "Transcrire mon acte de naissance etranger"),
    ("Kouassi N'guessan Guy", "Serge", "nguessanguysergekouassi@gmail.com", "+33627281201", "Renouvellement titre de sejour"),
    ("Pacome Wilfried", "Kouilly Gain", "wilfriedgain@gmail.com", "+33651866256", "TDS"),
    ("Ibrahime", "Toure", "ibrahimetoure@ymail.com", "+33783671181", "Titre de séjour"),
    ("EKANDJE Malobe franklyn", "Richard", "franklyn.malobe@yahoo.com", "+33627611772", "Renouvellement"),
    ("Mamitcho", "Masela", "mamitchomasela@gmail.com", "+33751249639", "TDS"),
    ("Kpoi Amani Brad", "Rony", "mrony89@yahoo.fr", "+33769688185", "Refus et oqtf"),
    ("Kara", "de Kara", "karadekara@live.fr", "+33613858408", "Naturalisation"),
    ("Ines", "Noor", "mina-meb@outlook.fr", "+33770334145", "Naturalisation"),
    ("Magagi", "Issa", "issamagagi@yahoo.fr", "+33699275267", "Oui"),
    ("Mohamed", "Diokhane", "mohamediokhane@gmail.com", "+33643322197", "Naturalisation"),
    ("Mikel", "Deen", "yillahosman10@gmail.com", "+33751477937", "Autre"),
    ("Curtis", "Zingoula", "curtiszingoula@gmail.com", "+33635715556", "Naturalisation"),
    ("Mahamadou", "", "mamadou6687@gmail.com", "+33759314617", "Renouvellement d’un titre de séjour expiré"),
    ("Bamba", "Souleymane", "bambasouleymanealex@gmail.com", "+33753807280", "Oui"),
    ("BIGUIZ", "", "toldoben@hotmail.fr", "+33768244071", "Naturalisation"),
    ("Cheikhou", "Kâ", "seikouka89@gmail.com", "+33779849521", "Changement de statut"),
    ("Jack", "Boris Fobain", "fobainboris@yahoo.fr", "+33788435429", "OQTF"),
    ("Clément", "Bothi Pouati", "rufinbot@yahoo.fr", "+33609106590", "Renouvellement"),
    ("Diao", "Ebadep", "ebadepdiao@yahoo.come", "+33753861275", "Renouvellement titre de séjour"),
    ("OZIA GUY", "Christian Lekpeli", "guychrist2012@yahoo.fr", "+33645090421", "Carte de séjour"),
    ("Edd", "Mzs", "eddymozese12@gmail.com", "+33753918034", "Autre"),
    ("Marie Jeanne", "Gnanzou", "mariejeannegnanzou@gmail.com", "+33952788856", "Naturalisation"),
    ("Wardi Ahamed", "Zaïmoudine", "zaimoudinewardi@gmail.com", "+262639992493", "Naturalisation"),
    ("Jean", "Wuta", "jeanwuta@yahoo.fr", "+33763158382", "Renouvellement titre de séjour"),
    ("Sangare", "Adama", "abdoulayesangare704@gmail.com", "+33753822140", "TDS"),

    # FAMILLE - REUNIR - PAPEX ENSEMBLE (20 leads)
    ("Romeo", "Penaye", "romeolepountouo@yahoo.com", "+33758710016", "Regroupement familial"),
    ("Arnaud", "Judi", "arnaudjudi@yahoo.fr", "+33753502964", "Autre"),
    ("Mumi Safira", "Balde", "safira.balde1990@gmail.com", "+33750501638", "Guiné-Bissau"),
    ("Marie-flore", "Koffi", "marie_flore9@yahoo.fr", "+33770463081", "Autre"),
    ("Maimouna", "Camara", "mounacra2110@gmail.com", "+33766158515", "Naturalisation"),
    ("Zeferino", "Venancio", "zefacio@yahoo.com", "+33766653983", "Regroupement familial"),
    ("Rony", "Da Costa", "ronydacosta77000@gmail.com", "+33758813252", "Agroupament familiares"),
    ("Kouakou", "Désirée", "dkouakou51@yahoo.fr", "+33783591320", "Regroupement familial"),
    ("Maria", "Monteiro", "monteirolurdes778@gmail.com", "+33764574878", "Autre"),
    ("THIAM", "SALLY", "salifthiam92@live.fr", "+33787059003", "Rennes"),
    ("Jocelyne", "Zandanga", "ludovicpierre_bourrelwanzane@yahoo.fr", "+33753187704", "Regroupement conjoint"),
    ("Princess", "de Passy", "asophietoho@hotmail.fr", "+33666628405", "Regroupement familial"),
    ("Esther", "Reine", "gayeetelle123@gmail.com", "+33758583794", "Autres"),
    ("Maximilien", "Simala", "max.simala@outlook.fr", "+33680455052", "Regroupement"),
    ("Mafoudia", "Sylla", "mafoudia79@yahoo.com", "+33757105167", "Regroupement familial"),
    ("Alida", "Akpa", "alidaakpa75@gmail.com", "+33784663031", "Regroupement familial (enfants)"),
    ("Fina", "Lopepe", "finalopepe37@gmail.com", "+33753131419", "Regroupement familial (enfant)"),
    ("Marie", "Ledun", "ledunmarie01@gmail.com", "+33784653889", "Naturalisation"),
    ("Lumbala", "Kabongo", "kabongo-john@outlook.fr", "+33753585918", "Regroupement familial"),

    # GREEN/RED FLAG - TDS - PAPEX CONSEILS (2 leads)
    ("Baouche", "Latamene", "baouche1@outlook.com", "+33784746595", "Demande de titre de séjour"),
    ("Karim", "Bourezg", "bourezg_karim@yahoo.com", "+33651671398", "Naturalisation"),

    # OBTENTION TDS - DEMANDE - PAPEX BOOST (20 leads)
    ("Melissa", "", "jessicafabiani99@gmail.com", "+33760081836", "Hi!"),
    ("Malak Sabrina", "Malak", "oussmezi16@yahoo.com", "+33616108895", "Titre de séjour"),
    ("Pedro", "Chow", "endou.ph@gmail.com", "+33771480367", "OQTF"),
    ("General", "Sk", "mondayaisosa750@gmail.com", "+33605635245", "TDS"),
    ("Lopes Fernandes Maria", "Estrela", "fernandesnorberta976@gmail.com", "+33695967972", "Titre de séjour"),
    ("Pokta", "Makyeay", "angathsoeung@gmail.com", "+33612399738", "TDS"),
    ("Jean Paul", "GOAH", "jeanpaul.goah@aol.com", "+33668837030", "Naturalisation"),
    ("Abderrahim", "Johri", "abdeljohri77@gmail.com", "+33679302699", "Johri"),
    ("Ngameni Hilary", "Francis", "hilovehilaryfrancis@gmail.com", "+33784798407", "TDS"),
    ("Kikangala", "Syllas", "merphysyllas.17@gmail.com", "+33646404816", "Contestation décision préfecture"),
    ("Kamal", "Akhoum", "kamalakhmoum1970@outlook.fr", "+33751087458", "TDS"),
    ("Rosine", "Guitton", "guittonrosine@gmail.com", "+33642704709", "Naturalisation"),
    ("Hassane", "Doumbia", "hassanedoumbia27@gmail.com", "+33773736295", "Titre de séjour"),
    ("Aboudou", "Ismaël", "mze.hamadi.noel@gmail.com", "+33666376425", "Renouvellement carte"),
    ("Zahid", "Ka Ka", "niazaizahid630@gmail.com", "+33754752995", "Nationalité"),
    ("Georges", "Mabenga", "georgesmabenga@gmail.com", "+33758859598", "TDS"),
    ("Georges Ricardeau", "GREGOIRE", "georgesricardeaugregoire@gmail.com", "+33695589607", "Naturalisation"),
    ("Yannick-Michel", "Nzogo", "ymz79@hotmail.fr", "+33753016030", "Titre de séjour"),
    ("Jacqueline", "Tiegninon", "jacqtieg1982@gmail.com", "+33678168932", "3 decembre 1976"),
    ("Francisco", "Muhongo", "muhongo@hotmail.fr", "+33783556570", "Renouvellement"),
]


def run():
    status = LeadStatus.objects.get(code=NEW_FACEBOOK_LEAD)
    author = User.objects.filter(id=SYSTEM_USER_ID).first()
    if not author:
        raise Exception("❌ Utilisateur système introuvable pour les commentaires")

    created_count = 0
    commented_count = 0

    for first_name, last_name, email, phone, besoin in LEADS:
        email_clean = (email or "").strip().lower()
        phone_clean = (phone or "").replace(" ", "")

        lead = Lead.objects.filter(
            Q(email__iexact=email_clean) |
            Q(phone=phone_clean)
        ).first()

        if not lead:
            lead = Lead.objects.create(
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email_clean or None,
                phone=phone_clean,
                status=status,
                source=LeadSource.FACEBOOK_ADS,
                created_at=timezone.now(),
            )
            created_count += 1
            print(f"✅ Lead créé: {lead}")

        # ➜ Création du commentaire besoin
        Comment.objects.create(
            lead=lead,
            author=author,
            content=f"Besoin prospect : {besoin}",
        )

        commented_count += 1
        print(f"💬 Commentaire ajouté: {lead}")

    print(f"\n🎉 {created_count} leads créés")
    print(f"💬 {commented_count} commentaires ajoutés")


if __name__ == "__main__":
    run()
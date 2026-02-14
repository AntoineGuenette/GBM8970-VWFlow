import pandas as pd
import matplotlib.pyplot as plt

# Paramètres
SEP = ";"        # séparateur CSV 
NTU_SCALE = 100  # facteur d’échelle, ici on met 100 si on veut un %
NTU_OFFSET = 0   # eau claire = 0 UTN


# Charger les fichiers

df_ref = pd.read_csv("eau.csv", sep=SEP)
df_sam = pd.read_csv("eau_farine.csv", sep=SEP)

# Nettoyage

df_ref.columns = df_ref.columns.str.strip()
df_sam.columns = df_sam.columns.str.strip()


# Conversion du temps en secondes

df_ref["time_s"] = df_ref["time_ms"] / 1000
df_sam["time_s"] = df_sam["time_ms"] / 1000


# Valeur de référence V0 (eau claire dans notre cas)
V0 = df_ref["Vdiff"].mean()
print(f"V0 (eau claire) = {V0:.6f} V")


# Calcul turbidité relative

df_sam["turb_rel"] = (V0 - df_sam["Vdiff"]) / V0


# Conversion en UTN

df_sam["NTU"] = NTU_SCALE * df_sam["turb_rel"] + NTU_OFFSET


# Graphiques

plt.figure(figsize=(8,4))
plt.plot(df_sam["time_s"], df_sam["NTU"], color="blue")
plt.xlabel("Temps (s)")
plt.ylabel("Turbidité relative (%)")
plt.title("Turbidité relative mesurée au cours du temps")
plt.grid(True)
plt.tight_layout()
plt.show()

# Print des datas

print(f"NTU moyenne = {df_sam['NTU'].mean():.2f}")
print(f"Écart-type NTU = {df_sam['NTU'].std():.2f}")

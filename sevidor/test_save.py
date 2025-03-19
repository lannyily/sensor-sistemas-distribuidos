"""
Script para testar se o servidor consegue salvar arquivos na pasta fotos
"""
import os
import sys
import datetime

# Definir o diretório de fotos
FOTOS_DIR = "fotos"

def test_save_file():
    """Testa se consegue salvar um arquivo na pasta fotos"""
    print("Testando salvar arquivo na pasta fotos...")
    
    # Verifica se o diretório existe, se não, cria
    if not os.path.exists(FOTOS_DIR):
        print(f"Criando diretório {FOTOS_DIR}")
        os.makedirs(FOTOS_DIR)
    
    # Cria um arquivo de teste
    test_file = os.path.join(FOTOS_DIR, f"teste_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    try:
        # Tenta escrever no arquivo
        with open(test_file, 'w') as f:
            f.write("Teste de escrita em arquivo\n")
            f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
        
        # Verifica se o arquivo foi criado
        if os.path.exists(test_file):
            size = os.path.getsize(test_file)
            print(f"✅ Arquivo criado com sucesso: {test_file} ({size} bytes)")
            
            # Lista os arquivos na pasta
            print("\nListando arquivos na pasta fotos:")
            for filename in os.listdir(FOTOS_DIR):
                filepath = os.path.join(FOTOS_DIR, filename)
                if os.path.isfile(filepath):
                    print(f"  - {filename} ({os.path.getsize(filepath)} bytes)")
            
            return True
        else:
            print(f"❌ Falha ao verificar arquivo após gravação: {test_file}")
            return False
    except Exception as e:
        print(f"❌ Erro ao salvar arquivo: {e}")
        return False

if __name__ == "__main__":
    success = test_save_file()
    sys.exit(0 if success else 1) 
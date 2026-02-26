import React from 'react';

interface LogoProps {
  size?: number;
}

const Logo: React.FC<LogoProps> = ({ size = 100 }) => {
  return (
    <div style={{ width: size, height: size, position: 'relative' }}>
      <img
        src="/logo.png"
        alt="ARAE Logo"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          opacity: 0.75,
        }}
      />
    </div>
  );
};

export default Logo;
